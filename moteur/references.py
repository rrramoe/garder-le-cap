"""Lecture des fichiers de référence (dossier `reference/`)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DOSSIER_REFERENCE = Path(__file__).resolve().parent.parent / "reference"


@lru_cache(maxsize=None)
def charger(nom: str) -> dict:
    chemin = DOSSIER_REFERENCE / f"{nom}.json"
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier de référence introuvable : reference/{nom}.json.")
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def sources(*cles: str) -> list[dict]:
    """Sources nommées, avec leur date et leur nature (`publie` ou `hypothese`)."""
    toutes = charger("sources")
    resultat = []
    for cle in dict.fromkeys(cles):
        if cle in toutes:
            resultat.append({"id": cle, **toutes[cle]})
    return resultat


def classe_politique(ticker: str) -> str | None:
    for cle, classe in charger("classes")["classes"].items():
        if ticker in classe["instruments"]:
            return cle
    return None


def encaisse() -> str:
    return charger("classes")["encaisse"]
