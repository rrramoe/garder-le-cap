"""Ce qu'un instrument apporterait au portefeuille d'un client : des faits, sans note ni verdict.

Mêmes conventions que les autres mesures du moteur : rendements quotidiens en CAD
(`donnees.rendements_cad`, jours sans cotation comptés à 0), même calendrier et même période,
portefeuille à poids constants rééquilibré chaque jour.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import donnees, instruments, notation, references
from .client import poids_par_classe

NB_PROCHES = 3


def _rendements(tickers: list[str]) -> pd.DataFrame:
    rend = donnees.rendements_cad()
    manquants = [t for t in tickers if t not in rend.columns]
    if manquants:
        raise donnees.ErreurDonnees(f"Instrument(s) sans données de prix : {', '.join(manquants)}.")
    return rend[tickers].fillna(0.0)


def rendement_portefeuille(port: dict) -> pd.Series:
    """Rendement quotidien du portefeuille à poids constants (même calcul que la contribution au risque)."""
    total = sum(port.values())
    w = pd.Series({t: v / total for t, v in port.items()})
    rend = _rendements(list(w.index))
    return pd.Series(rend.to_numpy() @ w.to_numpy(), index=rend.index)


def _correlation(a: pd.Series, b: pd.Series) -> float | None:
    if float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return None
    return float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])


def _etiquettes_vraies(ticker: str) -> list[str]:
    return [k for k, e in instruments.fiche(ticker)["etiquettes"].items() if e.get("valeur") is True]


def decrire(fiche_client: dict, ticker: str, pourcentage: float | None = None) -> dict:
    port = {t: float(w) for t, w in fiche_client["portefeuille_pct"].items()}
    f = instruments.fiche(ticker)
    r_instr = _rendements([ticker])[ticker]
    r_port = rendement_portefeuille(port)

    # Corrélation avec le portefeuille actuel.
    correlation = {"valeur": _correlation(r_instr, r_port), "deja_detenu_pct": port.get(ticker, 0.0),
                   "libelle": "Corrélation des rendements quotidiens de l'instrument avec ceux du portefeuille actuel"}

    # Positions actuelles les plus proches de l'instrument.
    autres = [t for t in port if t != ticker and port[t] > 0]
    rend_autres = _rendements(autres)
    proches = []
    for t in autres:
        c = _correlation(rend_autres[t], r_instr)
        if c is not None:
            proches.append({"ticker": t, "nom": instruments.fiche(t)["nom"], "poids_pct": port[t], "correlation": c})
    proches.sort(key=lambda x: -x["correlation"])

    # Exposition actuelle à ce qu'est l'instrument : classe, secteur, étiquettes.
    deduit = fiche_client["deduit"]
    classe = f["classe_politique"]
    fourchette = deduit["fourchettes_pct"]["valeur"].get(classe, {})
    plafonds = deduit["plafonds_concentration_pct"]["valeur"]
    exposition = {
        "classe": {"classe": classe, "poids_pct": poids_par_classe(port).get(classe, 0.0),
                   "min_pct": fourchette.get("min"), "cible_pct": fourchette.get("cible"),
                   "max_pct": fourchette.get("max")},
        "secteur": None,
        "etiquettes": {},
    }
    if instruments.est_action_individuelle(ticker):
        meme = {t: w for t, w in port.items() if w > 0 and instruments.est_action_individuelle(t)
                and instruments.fiche(t)["secteur"] == f["secteur"]}
        exposition["secteur"] = {"secteur": f["secteur"], "poids_pct": sum(meme.values()), "positions": meme,
                                 "plafond_pct": plafonds["secteur"],
                                 "plafond_action_individuelle_pct": plafonds["action_individuelle"]}
    elif instruments.est_fonds(ticker):
        exposition["fonds"] = {"poids_actuel_pct": port.get(ticker, 0.0),
                               "plafond_pct": plafonds["fonds_negocie_en_bourse"]}
    themes = {t["etiquette"]: t["id"] for t in references.charger("themes")["themes"]}
    reponses = fiche_client["questionnaire"].get("themes", {})
    for etiquette in _etiquettes_vraies(ticker):
        detenus = {t: w for t, w in port.items() if w > 0 and instruments.valeur_etiquette(t, etiquette) is True}
        bloc = {"poids_pct": sum(detenus.values()), "positions": detenus,
                "reponse_client": reponses.get(themes.get(etiquette, etiquette)), "plafond_pct": None}
        if etiquette == "crypto":
            bloc["plafond_pct"] = deduit["crypto_pct"]["valeur"]["plafond_pct"]
        exposition["etiquettes"][etiquette] = bloc

    # Après l'ordre (achat au comptant), part du portefeuille et part du risque.
    apres = None
    if pourcentage is not None:
        avant = notation.contribution_risque(port, ticker)
        try:
            port_apres = notation.appliquer_ordre(port, ticker, "achat", pourcentage)
            c = notation.contribution_risque(port_apres, ticker)
            apres = {"pourcentage_ordre": float(pourcentage), "poids_pct": c["poids_pct"],
                     "part_du_risque_pct": c["part_du_risque_pct"], "poids_avant_pct": avant["poids_pct"],
                     "part_du_risque_avant_pct": avant["part_du_risque_pct"]}
        except notation.ErreurOrdre as e:  # par exemple encaisse insuffisante : le reste reste valable
            apres = {"pourcentage_ordre": float(pourcentage), "erreur": str(e)}

    # Candidats de la même classe, du plus proche au plus éloigné de l'instrument.
    univers = [t for t, g in instruments.toutes().items() if g["classe_politique"] == classe and t != ticker]
    rend_cand = _rendements(univers)
    candidats = []
    for t in univers:
        g = instruments.fiche(t)
        candidats.append({
            "symbole": t, "nom": g["nom"], "secteur": g["secteur"],
            "correlation_avec_instrument": _correlation(rend_cand[t], r_instr),
            "correlation_avec_portefeuille": _correlation(rend_cand[t], r_port),
            "volatilite_annualisee": g["statistiques_cad"]["volatilite_annualisee"],
            "pire_baisse": g["statistiques_cad"]["pire_baisse"],
            "etiquettes": {k: e["valeur"] for k, e in g["etiquettes"].items()},
            "deja_detenu_pct": port.get(t, 0.0),
        })
    candidats.sort(key=lambda x: -(x["correlation_avec_instrument"] if x["correlation_avec_instrument"] is not None
                                   else -2.0))

    return {
        "ticker": ticker, "nom": f["nom"], "classe_politique": classe, "secteur": f["secteur"],
        "etiquettes_vraies": _etiquettes_vraies(ticker),
        "correlation_portefeuille": correlation,
        "positions_proches": proches[:NB_PROCHES],
        "exposition_actuelle": exposition,
        "apres_ordre": apres,
        "candidats": candidats,
    }
