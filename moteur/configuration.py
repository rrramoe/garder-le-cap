"""Configuration locale des ressources AWS (garde-fou Bedrock, bucket S3), hors du dépôt.

Les noms des ressources viennent de variables d'environnement. Si elles manquent, on les lit dans
le fichier local `glc.env` à la racine du dépôt (ignoré par git ; chemin modifiable par la variable
`GLC_CONFIG`). Le fichier d'exemple `glc.env.exemple` liste les variables, sans valeurs.
Une variable déjà présente dans l'environnement l'emporte sur le fichier.
"""
from __future__ import annotations

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_DEFAUT = RACINE / "glc.env"
VARIABLES = ("GLC_GARDE_FOU_ID", "GLC_GARDE_FOU_VERSION", "GLC_BUCKET")


def chemin_fichier() -> Path:
    return Path(os.environ.get("GLC_CONFIG") or FICHIER_DEFAUT).expanduser()


def lire_fichier(chemin: Path | None = None) -> dict:
    """Lignes `CLE=valeur` (ou `export CLE=valeur`) du fichier local ; {} s'il n'existe pas."""
    chemin = chemin or chemin_fichier()
    valeurs = {}
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines() if chemin.is_file() else []
    except OSError:
        lignes = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne.startswith("export "):
            ligne = ligne[len("export "):].strip()
        cle, egal, valeur = ligne.partition("=")
        cle, valeur = cle.strip(), valeur.strip()
        if not egal or not cle.startswith("GLC_"):
            continue
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "'\"":
            valeur = valeur[1:-1]
        valeurs[cle] = valeur
    return valeurs


def valeur(nom: str) -> str | None:
    """Valeur d'une variable : environnement d'abord, puis fichier local. None si absente ou vide."""
    v = os.environ.get(nom)
    if v is None:
        v = lire_fichier().get(nom)
    return v.strip() if v and v.strip() else None


def ecrire_valeurs(nouvelles: dict, chemin: Path | None = None) -> Path:
    """Met à jour (ou ajoute) des variables dans le fichier local, sans toucher aux autres lignes."""
    chemin = chemin or chemin_fichier()
    lignes = chemin.read_text(encoding="utf-8").splitlines() if chemin.is_file() else [
        "# Configuration locale de Garder le cap : noms des ressources AWS. Ne pas publier."]
    restantes = dict(nouvelles)
    resultat = []
    for ligne in lignes:
        cle = ligne.strip().removeprefix("export ").partition("=")[0].strip()
        if cle in restantes:
            resultat.append(f"{cle}={restantes.pop(cle)}")
        else:
            resultat.append(ligne)
    resultat += [f"{cle}={v}" for cle, v in restantes.items()]
    chemin.write_text("\n".join(resultat) + "\n", encoding="utf-8")
    return chemin
