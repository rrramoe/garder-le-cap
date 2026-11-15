"""Chargement des identifiants AWS temporaires, hors du dépôt.

Si les variables AWS manquent dans l'environnement, on lit le fichier `~/.aws/datathon.env`
(lignes `export AWS_...=...` copiées depuis Workshop Studio ; chemin modifiable par la variable
`GLC_AWS_ENV`) et on les place dans l'environnement du processus. Aucune valeur n'est affichée
ni journalisée.
"""
from __future__ import annotations

import os
from pathlib import Path

REGION = "us-east-1"
FICHIER_DEFAUT = Path.home() / ".aws" / "datathon.env"
VARIABLES_CLES = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


def chemin_fichier() -> Path:
    return Path(os.environ.get("GLC_AWS_ENV") or FICHIER_DEFAUT).expanduser()


def _lire(chemin: Path) -> dict:
    valeurs = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne.startswith("export "):
            ligne = ligne[len("export "):].strip()
        cle, egal, valeur = ligne.partition("=")
        cle, valeur = cle.strip(), valeur.strip()
        if not egal or not cle.startswith("AWS_"):
            continue
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "'\"":
            valeur = valeur[1:-1]
        valeurs[cle] = valeur
    return valeurs


def charger_identifiants() -> bool:
    """Place les identifiants dans l'environnement au besoin. Renvoie True s'ils sont présents."""
    if not all(os.environ.get(v) for v in VARIABLES_CLES):
        chemin = chemin_fichier()
        try:
            valeurs = _lire(chemin) if chemin.is_file() else {}
        except OSError:
            valeurs = {}
        for cle, valeur in valeurs.items():
            os.environ[cle] = valeur
    os.environ.setdefault("AWS_REGION", REGION)
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)
    return all(os.environ.get(v) for v in VARIABLES_CLES)


def identifiants_disponibles() -> bool:
    """True si boto3 trouve des identifiants (environnement, fichier du Datathon ou configuration AWS)."""
    if charger_identifiants():
        return True
    try:
        import boto3
        return boto3.Session().get_credentials() is not None
    except Exception:
        return False
