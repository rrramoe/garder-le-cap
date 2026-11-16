"""Les cours passés, pour donner à voir : une ligne par titre, la valeur du portefeuille, la variation sur un an.

Tout vient de l'historique de prix que le moteur lit déjà (lecture seule). Rien n'est un cours en direct :
chaque courbe couvre la dernière année de l'historique, et l'interface le dit.
"""

from __future__ import annotations

import streamlit as st

SEANCES = 252   # une année de séances
POINTS = 64     # points gardés par courbe
PERIODE = "un an"


@st.cache_data(show_spinner=False)
def _cours() -> dict:
    """{titre: [cours en dollars canadiens, du plus ancien au plus récent]} sur la dernière année, allégé."""
    try:
        from moteur import donnees
        prix = donnees.prix_cad().ffill().tail(SEANCES + 1)
    except Exception:
        return {}
    pas = max(1, len(prix) // POINTS)
    lignes = list(range(len(prix) - 1, -1, -pas))[::-1]
    return {str(t): [float(v) for v in prix[t].iloc[lignes]] for t in prix.columns if prix[t].notna().all()}


def cours(titre: str) -> list[float]:
    return _cours().get(titre, [])


def variation(serie: list[float]) -> float | None:
    """La variation de la série sur sa période, en pourcentage."""
    if len(serie) < 2 or not serie[0]:
        return None
    return (serie[-1] / serie[0] - 1) * 100


def valeur_du_portefeuille(portefeuille_pct: dict, valeur: float) -> list[float]:
    """La valeur qu'aurait eue le portefeuille d'aujourd'hui sur la période, à composition constante en titres :
    la même hypothèse que les notes de risque (le portefeuille tel quel, rejoué sur le passé)."""
    tous = _cours()
    series = {t: tous[t] for t in portefeuille_pct if t in tous}
    if not series:
        return []
    n = min(len(s) for s in series.values())
    couvert = sum(float(w) for t, w in portefeuille_pct.items() if t in series)
    if couvert <= 0:
        return []
    return [sum(float(portefeuille_pct[t]) / couvert * s[-n + i] / s[-1] for t, s in series.items()) * valeur
            for i in range(n)]
