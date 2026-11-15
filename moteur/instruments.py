"""Accès aux fiches d'instruments mises en cache (`reference/fiches_instruments.json`, lu comme les autres
fichiers de référence : dans le bucket S3 s'il est configuré, sinon dans le dossier local)."""
from __future__ import annotations

from functools import lru_cache

from . import references
from .references import DOSSIER_REFERENCE

CHEMIN_FICHES = DOSSIER_REFERENCE / "fiches_instruments.json"


class ErreurInstrument(Exception):
    pass


@lru_cache(maxsize=1)
def _cache() -> dict:
    try:
        return references.charger(CHEMIN_FICHES.stem)
    except FileNotFoundError:
        raise ErreurInstrument(
            "Les fiches d'instruments sont introuvables (reference/fiches_instruments.json). "
            "Construisez-les avec `python scripts/construire_fiches.py`."
        ) from None


def toutes() -> dict:
    return _cache()["instruments"]


def meta() -> dict:
    c = _cache()
    return {k: v for k, v in c.items() if k != "instruments"}


def fiche(ticker: str) -> dict:
    f = toutes().get(ticker)
    if f is None:
        raise ErreurInstrument(f"Instrument inconnu : « {ticker} ». Il ne fait pas partie de l'univers des 31 actifs.")
    return f


def valeur_etiquette(ticker: str, etiquette: str):
    """`True`, `False`, `"indetermine"` ou `"sans_objet"`. Étiquette absente : `indetermine`."""
    e = fiche(ticker)["etiquettes"].get(etiquette)
    return "indetermine" if e is None else e["valeur"]


def est_action_individuelle(ticker: str) -> bool:
    return fiche(ticker)["classe_actif"] == "equity"


def est_fonds(ticker: str) -> bool:
    return fiche(ticker)["classe_actif"].startswith("etf_")
