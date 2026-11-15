"""Couche de données : prix en dollars canadiens et mesures de risque.

Conventions (section 4 de la spécification) :
- rendements calculés à partir de `adj_close` ;
- tout en CAD : un actif en USD est multiplié par `usdcad` du même jour ;
- calendrier : jours où `XIU.TO` ou `SPY` a un prix ; prix et taux de change
  reportés en avant sur ce calendrier, cryptos comprises ;
- portefeuille à poids constants, rééquilibré chaque jour ;
- volatilité annualisée = écart-type quotidien x racine(252) ;
- pire baisse = minimum de valeur / sommet précédent - 1 ;
- temps sous l'eau = plus longue période (en années) sous le sommet précédent,
  marquée `non_recupere` si elle est encore ouverte à la fin des données.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
TICKERS_CALENDRIER = ("XIU.TO", "SPY")
JOURS_PAR_AN = 252
JOURS_CIVILS_PAR_AN = 365.25


class ErreurDonnees(Exception):
    """Erreur de données, avec un message en français destiné à l'utilisateur."""


def dossier_donnees() -> Path:
    env = os.environ.get("GLC_DATA_DIR")
    return Path(env) if env else RACINE / "data"


def _lire_csv(nom: str) -> pd.DataFrame:
    chemin = dossier_donnees() / nom
    if not chemin.exists():
        if nom == "prices_daily.csv":
            raise ErreurDonnees(
                f"Le fichier des prix est introuvable ({chemin}). Il n'est pas publié dans "
                "le dépôt (conditions d'utilisation de Yahoo) : régénérez-le avec "
                "`python data/build_dataset.py`, ou copiez-le dans `data/` "
                "(ou dans le dossier indiqué par la variable GLC_DATA_DIR)."
            )
        raise ErreurDonnees(f"Fichier de données introuvable : {chemin}.")
    return pd.read_csv(chemin)


@lru_cache(maxsize=4)
def _univers_cache(dossier: str) -> pd.DataFrame:
    return _lire_csv("assets_universe.csv").set_index("ticker")


def univers() -> pd.DataFrame:
    """Univers des 31 actifs, indexé par ticker."""
    return _univers_cache(str(dossier_donnees()))


@lru_cache(maxsize=4)
def _prix_cad_cache(dossier: str) -> pd.DataFrame:
    prix = _lire_csv("prices_daily.csv")
    fx = _lire_csv("fx_usdcad_daily.csv")
    prix["date"] = pd.to_datetime(prix["date"])
    fx["date"] = pd.to_datetime(fx["date"])

    calendrier = pd.DatetimeIndex(
        sorted(prix.loc[prix["ticker"].isin(TICKERS_CALENDRIER), "date"].unique())
    )
    if len(calendrier) == 0:
        raise ErreurDonnees("Aucun prix pour XIU.TO ni SPY : impossible de bâtir le calendrier.")

    larges = prix.pivot_table(index="date", columns="ticker", values="adj_close", aggfunc="last")
    toutes_dates = larges.index.union(calendrier)
    larges = larges.reindex(toutes_dates).ffill().reindex(calendrier)

    taux = fx.set_index("date")["usdcad"].sort_index()
    taux = taux.reindex(taux.index.union(calendrier)).ffill().reindex(calendrier)

    devises = univers()["currency"]
    for ticker in larges.columns:
        if devises.get(ticker) == "USD":
            larges[ticker] = larges[ticker] * taux
    return larges


def prix_cad() -> pd.DataFrame:
    """Prix ajustés en CAD, sur le calendrier commun, reportés en avant."""
    return _prix_cad_cache(str(dossier_donnees()))


def rendements_cad() -> pd.DataFrame:
    return prix_cad().pct_change().iloc[1:]


def periode() -> dict:
    p = prix_cad()
    return {"debut": p.index[0].date().isoformat(), "fin": p.index[-1].date().isoformat()}


def valeur_portefeuille(poids: dict[str, float]) -> pd.Series:
    """Valeur d'un portefeuille à poids constants, rééquilibré chaque jour (base 1).

    `poids` : ticker -> poids (en fraction ou en %, normalisé ici).
    """
    poids = {t: float(w) for t, w in poids.items() if abs(float(w)) > 1e-12}
    total = sum(poids.values())
    if total <= 0:
        raise ErreurDonnees("Portefeuille vide : aucun poids positif.")
    rend = rendements_cad()
    manquants = [t for t in poids if t not in rend.columns]
    if manquants:
        raise ErreurDonnees(f"Instrument(s) sans données de prix : {', '.join(manquants)}.")
    w = pd.Series(poids) / total
    r = rend[w.index].fillna(0.0).to_numpy() @ w.to_numpy()
    valeur = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    return pd.Series(valeur, index=prix_cad().index)


def volatilite_annualisee(valeur: pd.Series) -> float:
    return float(valeur.pct_change().iloc[1:].std() * np.sqrt(JOURS_PAR_AN))


def pire_baisse(valeur: pd.Series) -> float:
    return float((valeur / valeur.cummax() - 1.0).min())


def temps_sous_l_eau(valeur: pd.Series) -> dict:
    """Plus longue période sous le sommet précédent, en années civiles.

    La période va du dernier sommet au premier jour où la valeur le retrouve.
    Si elle est encore ouverte à la fin, elle compte jusqu'à la dernière date et
    `non_recupere` vaut True.
    """
    sommet = valeur.cummax()
    sous = (valeur < sommet).to_numpy()
    dates = valeur.index
    meilleur = {"annees": 0.0, "debut": None, "fin": None, "non_recupere": False}
    i, n = 0, len(valeur)
    while i < n:
        if sous[i]:
            debut = i - 1  # jour du sommet
            j = i
            while j < n and sous[j]:
                j += 1
            ouvert = j >= n
            fin = n - 1 if ouvert else j
            duree = (dates[fin] - dates[debut]).days / JOURS_CIVILS_PAR_AN
            if duree > meilleur["annees"]:
                meilleur = {
                    "annees": float(duree),
                    "debut": dates[debut].date().isoformat(),
                    "fin": dates[fin].date().isoformat(),
                    "non_recupere": bool(ouvert),
                }
            i = j
        else:
            i += 1
    return meilleur


def statistiques(poids: dict[str, float]) -> dict:
    v = valeur_portefeuille(poids)
    tsl = temps_sous_l_eau(v)
    return {
        "volatilite_annualisee": volatilite_annualisee(v),
        "pire_baisse": pire_baisse(v),
        "temps_sous_l_eau_annees": tsl["annees"],
        "temps_sous_l_eau_debut": tsl["debut"],
        "temps_sous_l_eau_fin": tsl["fin"],
        "non_recupere": tsl["non_recupere"],
    }
