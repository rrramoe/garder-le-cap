"""Profils des instruments hors des données des organisateurs (fiche du titre, partie B).

Lus dans `reference/profils_instruments.json` (bucket S3 privé s'il est configuré, sinon dossier local),
fichier construit par `scripts/profils_instruments.py` à partir de Yahoo Finance (yfinance) et non publié
dans le dépôt. Absent : chaque profil vaut « indetermine ».
"""
from __future__ import annotations

from . import references

INDET = "indetermine"


def _profils() -> dict | None:
    try:
        return references.charger("profils_instruments")["profils"]
    except FileNotFoundError:
        return None


def profil(ticker: str) -> dict:
    p = _profils()
    if p is None:
        return {"type": INDET, "raison": "Profils non construits (scripts/profils_instruments.py)."}
    return p.get(ticker, {"type": INDET, "raison": "Instrument absent des profils."})


def symbole_univers(symbole: str, univers: set, fonds: str) -> str | None:
    """Symbole d'une position de fonds ramené à l'univers (« RY » d'un fonds canadien → « RY.TO »)."""
    if symbole in univers:
        return symbole
    if fonds.endswith(".TO") and f"{symbole}.TO" in univers:
        return f"{symbole}.TO"
    return None


def positions_deja_detenues(fonds: str, port: dict, univers: set) -> dict | str:
    """Parmi les dix plus grandes positions du fonds, celles que le client détient déjà en direct."""
    positions = profil(fonds).get("dix_plus_grandes_positions")
    if not isinstance(positions, list):
        return INDET
    communs = []
    for h in positions:
        t = symbole_univers(h["symbole"], univers, fonds)
        if t and port.get(t, 0) > 0:
            communs.append({"symbole": t, "poids_dans_le_fonds": h["poids"], "poids_chez_le_client_pct": port[t]})
    return {"part_du_fonds": round(sum(c["poids_dans_le_fonds"] for c in communs), 6), "titres": communs}
