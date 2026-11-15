"""Faits de marché d'un instrument, tirés des fichiers des organisateurs (fiche du titre, partie A).

Des descriptions, jamais des notes : rien ici n'entre dans un score. Conventions du moteur (`donnees.py`) :
prix ajustés `adj_close`, en CAD, sur le calendrier commun (jours où XIU.TO ou SPY a un prix), reportés en
avant. Exceptions, nommées dans chaque bloc : les dividendes, les fractionnements et la liquidité sont dans la
devise de cotation ; la sensibilité aux taux se lit sur des rendements hebdomadaires (vendredi), pour aligner
le calendrier des taux sur celui des prix. Une donnée absente ou trop courte donne « indetermine ».

Fichiers lus dans `data/` : prices_daily.csv, fx_usdcad_daily.csv, assets_universe.csv (déjà utilisés),
corporate_actions.csv et macro_rates.csv (non publiés dans le dépôt, comme les prix).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import donnees

INDET = "indetermine"
REFERENCES_MARCHE = {"XIU.TO": "actions_canada", "SPY": "actions_etats_unis", "XBB.TO": "obligations_canada"}
MARCHE_ANNEE = "XIU.TO"          # « le marché » pour l'année la plus difficile (hypothèse, en CAD)
SEUIL_BAISSE = 0.20              # baisses de plus de 20 %
JOURS_LIQUIDITE = 63             # environ trois mois de séances
TAUX_10_ANS = {"CAD": "BD.CDN.10YR.DQ.YLD", "USD": "DGS10"}
MIN_OBS = 60                     # observations minimales pour une corrélation ou un bêta


def _r(x, d=6):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), d)


@lru_cache(maxsize=2)
def _brut(dossier: str) -> pd.DataFrame:
    p = pd.read_csv(donnees.dossier_donnees() / "prices_daily.csv")
    p["date"] = pd.to_datetime(p["date"])
    return p


@lru_cache(maxsize=2)
def _actions(dossier: str) -> pd.DataFrame | None:
    chemin = donnees.dossier_donnees() / "corporate_actions.csv"
    if not chemin.exists():
        return None
    a = pd.read_csv(chemin)
    a["ex_date"] = pd.to_datetime(a["ex_date"])
    return a


@lru_cache(maxsize=2)
def _taux(dossier: str) -> pd.DataFrame | None:
    chemin = donnees.dossier_donnees() / "macro_rates.csv"
    if not chemin.exists():
        return None
    m = pd.read_csv(chemin)
    m["date"] = pd.to_datetime(m["date"])
    return m


def _cle() -> str:
    return str(donnees.dossier_donnees())


def disponibilite() -> dict:
    """Fichiers facultatifs présents ou non (les blocs qui en dépendent sont « indetermine » sinon)."""
    d = donnees.dossier_donnees()
    return {"corporate_actions.csv": (d / "corporate_actions.csv").exists(), "macro_rates.csv": (d / "macro_rates.csv").exists()}


# ---------------------------------------------------------------- performance passée

def annees_civiles(prix: pd.Series) -> dict:
    """Rendement de chaque année civile : dernier prix de l'année / dernier prix de l'année précédente - 1.

    La première année part du premier prix disponible et la dernière s'arrête au dernier : elles sont partielles.
    """
    prix = prix.dropna()
    fins = prix.groupby(prix.index.year).last()
    debut = prix.iloc[0]
    res = {}
    prec = debut
    for an, fin in fins.items():
        res[int(an)] = {"rendement": _r(fin / prec - 1), "partielle": bool(an == prix.index[0].year or an == prix.index[-1].year)}
        prec = fin
    return res


def performance(ticker: str) -> dict:
    p = donnees.prix_cad()
    prix = p[ticker].dropna()
    if len(prix) < 2:
        return {"valeur": INDET}
    annees = annees_civiles(prix)
    completes = {a: v["rendement"] for a, v in annees.items() if not v["partielle"]}
    marche = annees_civiles(p[MARCHE_ANNEE].dropna())
    marche_completes = {a: v["rendement"] for a, v in marche.items() if not v["partielle"]}
    pire_marche = min(marche_completes, key=marche_completes.get) if marche_completes else None
    return {
        "rendement_total": _r(prix.iloc[-1] / prix.iloc[0] - 1),
        "par_annee": {str(a): v["rendement"] for a, v in annees.items()},
        "annees_partielles": [a for a, v in annees.items() if v["partielle"]],
        "meilleure_annee": ({"annee": max(completes, key=completes.get), "rendement": max(completes.values())}
                            if completes else INDET),
        "pire_annee": ({"annee": min(completes, key=completes.get), "rendement": min(completes.values())}
                       if completes else INDET),
        "annee_difficile_du_marche": ({"annee": pire_marche, "marche": MARCHE_ANNEE,
                                       "rendement_marche": marche_completes[pire_marche],
                                       "rendement": completes.get(pire_marche, INDET)} if pire_marche else INDET),
        "ecart_au_plus_haut": _r(prix.iloc[-1] / prix.max() - 1),
        "date_plus_haut": prix.idxmax().date().isoformat(),
        "unite": "fraction, rendement total en CAD (dividendes compris)",
        "note": "Meilleure et pire année : années civiles complètes seulement.",
    }


# ---------------------------------------------------------------- risque

def volatilite_baissiere(r: pd.Series) -> float:
    """Racine de la moyenne des carrés des rendements négatifs (zéro sinon), annualisée par racine(252)."""
    return float(np.sqrt(np.mean(np.minimum(r.to_numpy(), 0.0) ** 2)) * np.sqrt(donnees.JOURS_PAR_AN))


def baisses_au_dela(prix: pd.Series, seuil: float = SEUIL_BAISSE) -> int:
    """Nombre d'épisodes où le prix tombe à plus de `seuil` sous son sommet précédent.

    Un épisode commence au premier jour sous le seuil et se termine quand le prix retrouve son sommet.
    """
    sommet = prix.cummax()
    n, dans_episode = 0, False
    for v, s in zip(prix.to_numpy(), sommet.to_numpy()):
        if v >= s:
            dans_episode = False
        elif v / s - 1 < -seuil and not dans_episode:
            n += 1
            dans_episode = True
    return n


def risque(ticker: str) -> dict:
    prix = donnees.prix_cad()[ticker].dropna()
    r = prix.pct_change().dropna()
    if len(r) < MIN_OBS:
        return {"valeur": INDET}
    mensuel = prix.resample("ME").last().pct_change().dropna()
    return {
        "volatilite_baissiere": _r(volatilite_baissiere(r)),
        "pire_jour": {"date": r.idxmin().date().isoformat(), "rendement": _r(r.min())},
        "pire_mois": ({"mois": mensuel.idxmin().strftime("%Y-%m"), "rendement": _r(mensuel.min())}
                      if len(mensuel) else INDET),
        "baisses_de_plus_de_20_pct": baisses_au_dela(prix),
        "unite": "fraction annualisée (volatilité), fraction (jour, mois), nombre d'épisodes ; en CAD",
    }


# ---------------------------------------------------------------- lien avec les marchés

def beta_correlation(r: pd.Series, m: pd.Series) -> dict:
    d = pd.concat([r, m], axis=1).dropna()
    if len(d) < MIN_OBS or d.iloc[:, 1].var() == 0:
        return {"beta": INDET, "correlation": INDET}
    a, b = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    return {"beta": _r(np.cov(a, b, ddof=1)[0, 1] / np.var(b, ddof=1), 4),
            "correlation": _r(np.corrcoef(a, b)[0, 1], 4)}


def prix_locaux() -> pd.DataFrame:
    """Prix ajustés dans la devise de cotation, sur le calendrier du moteur, reportés en avant."""
    brut = _brut(_cle())
    larges = brut.pivot_table(index="date", columns="ticker", values="adj_close", aggfunc="last")
    cal = donnees.prix_cad().index
    return larges.reindex(larges.index.union(cal)).ffill().reindex(cal)


def part_change(r_cad: pd.Series, r_local: pd.Series) -> float | None:
    """Part de la variance en CAD qui vient du taux de change : 1 - variance locale / variance en CAD.

    Négative quand le change a amorti les mouvements (le dollar américain monte souvent quand les actions baissent).
    """
    d = pd.concat([r_cad, r_local], axis=1).dropna()
    v_cad = d.iloc[:, 0].var()
    if len(d) < MIN_OBS or not v_cad:
        return None
    return float(1 - d.iloc[:, 1].var() / v_cad)


def marches(ticker: str, devise: str) -> dict:
    rend = donnees.rendements_cad()
    r = rend[ticker]
    res = {nom: beta_correlation(r, rend[ref]) for ref, nom in REFERENCES_MARCHE.items()}
    res["references"] = {nom: ref for ref, nom in REFERENCES_MARCHE.items()}
    if devise == "USD":
        loc = prix_locaux()[ticker].pct_change().iloc[1:]
        pc = part_change(r, loc)
        res["part_volatilite_due_au_change"] = _r(pc, 4) if pc is not None else INDET
    else:
        res["part_volatilite_due_au_change"] = "sans_objet"
    res["unite"] = "rendements quotidiens en CAD ; bêta et corrélation sans unité ; part du change en fraction de la variance"
    return res


# ---------------------------------------------------------------- revenu

def revenu(ticker: str) -> dict:
    a = _actions(_cle())
    if a is None:
        return {"valeur": INDET, "raison": "corporate_actions.csv absent de data/"}
    brut = _brut(_cle())
    lignes = brut[brut["ticker"] == ticker].sort_values("date")
    if lignes.empty:
        return {"valeur": INDET}
    fin = lignes["date"].iloc[-1]
    dernier = float(lignes["close"].iloc[-1])
    devise = str(lignes["currency"].iloc[-1])
    div = a[(a["ticker"] == ticker) & (a["action"] == "dividend")]
    splits = a[(a["ticker"] == ticker) & (a["action"] == "split")]
    d12 = float(div.loc[div["ex_date"] > fin - pd.DateOffset(months=12), "value"].sum())
    par_an = div.groupby(div["ex_date"].dt.year)["value"].sum()
    debut_an, fin_an = lignes["date"].iloc[0].year, fin.year
    completes = par_an[(par_an.index > debut_an) & (par_an.index < fin_an)]
    if len(completes) >= 2:
        croissance = bool(completes.iloc[-1] > completes.iloc[0])
    else:
        croissance = INDET
    return {
        "dividendes_12_mois": _r(d12, 4),
        "rendement_dividende": _r(d12 / dernier, 4) if dernier > 0 else INDET,
        "annees_avec_dividende": int((par_an > 0).sum()),
        "dividende_en_hausse": croissance,
        "dividende_par_annee": {str(int(k)): _r(v, 4) for k, v in par_an.items()},
        "fractionnements": [{"date": d.date().isoformat(), "ratio": _r(v, 4)} for d, v in zip(splits["ex_date"], splits["value"])],
        "devise": devise,
        "unite": "dividendes par action en devise de cotation ; rendement = dividendes des 12 derniers mois / dernier cours",
        "note": "Années civiles de la période ; « en hausse » compare la dernière année complète à la première. "
                "Les dividendes des fonds peuvent être incomplets (organisateurs).",
    }


# ---------------------------------------------------------------- liquidité

def liquidite(ticker: str, classe_actif: str) -> dict:
    brut = _brut(_cle())
    lignes = brut[brut["ticker"] == ticker].sort_values("date").tail(JOURS_LIQUIDITE)
    if len(lignes) < 20:
        return {"valeur": INDET}
    # Crypto : Yahoo donne le volume en dollars américains échangés, pas en unités.
    valeur = lignes["volume"] if classe_actif == "crypto" else lignes["close"] * lignes["volume"]
    moyenne = float(valeur.mean())
    devise = str(lignes["currency"].iloc[-1])
    taux = 1.0
    if devise == "USD":
        fx = pd.read_csv(donnees.dossier_donnees() / "fx_usdcad_daily.csv")
        taux = float(fx["usdcad"].iloc[-1])
    return {
        "valeur_echangee_moyenne_par_jour": _r(moyenne, 0),
        "valeur_echangee_moyenne_par_jour_cad": _r(moyenne * taux, 0),
        "devise": devise,
        "periode": {"debut": lignes["date"].iloc[0].date().isoformat(), "fin": lignes["date"].iloc[-1].date().isoformat(),
                    "seances": int(len(lignes))},
        "unite": "dollars par séance (cours de clôture x volume ; crypto : volume déjà en dollars américains)",
    }


def jours_de_volume(montant_cad: float, liquidite_bloc: dict) -> float | str:
    v = liquidite_bloc.get("valeur_echangee_moyenne_par_jour_cad") if isinstance(liquidite_bloc, dict) else None
    if not v:
        return INDET
    return round(float(montant_cad) / float(v), 6)


# ---------------------------------------------------------------- taux

def sensibilite_taux(ticker: str, devise: str) -> dict:
    m = _taux(_cle())
    serie_id = TAUX_10_ANS.get(devise, "DGS10")
    if m is None:
        return {"valeur": INDET, "raison": "macro_rates.csv absent de data/"}
    t = m[m["series_id"] == serie_id].set_index("date")["value"].sort_index()
    prix = donnees.prix_cad()[ticker].dropna()
    hebdo = pd.concat([prix.resample("W-FRI").last().pct_change(), t.resample("W-FRI").last().diff()], axis=1).dropna()
    if len(hebdo) < 52:
        return {"valeur": INDET}
    c = np.corrcoef(hebdo.iloc[:, 0], hebdo.iloc[:, 1])[0, 1]
    return {"correlation_avec_taux_10_ans": _r(c, 4), "serie": serie_id, "semaines": int(len(hebdo)),
            "unite": "corrélation des rendements hebdomadaires en CAD avec la variation hebdomadaire du taux 10 ans "
                     "(points de pourcentage)"}


# ---------------------------------------------------------------- tout

def faits(ticker: str, ligne: dict) -> dict:
    """Bloc compact `faits_marche` d'une fiche d'instrument."""
    p = donnees.periode()
    return {
        "periode": p,
        "performance": performance(ticker),
        "risque": risque(ticker),
        "marches": marches(ticker, ligne["currency"]),
        "revenu": revenu(ticker),
        "liquidite": liquidite(ticker, ligne["asset_class"]),
        "taux": sensibilite_taux(ticker, ligne["currency"]),
        "sources": list(SOURCES),
    }


SOURCES = ("donnees_marche", "donnees_dividendes", "donnees_taux", "hypothese_faits_marche")
