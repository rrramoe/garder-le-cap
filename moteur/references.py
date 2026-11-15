"""Lecture des fichiers de référence : bucket S3 privé si `GLC_BUCKET` est configuré, sinon `reference/`.

Le bucket est créé et rempli par `scripts/creer_bucket.py`. Si S3 ne répond pas (identifiants absents
ou expirés, réseau), le fichier local est lu et `origine()` le dit. Chaque fichier n'est lu qu'une fois.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import configuration

DOSSIER_REFERENCE = Path(__file__).resolve().parent.parent / "reference"
REGION = "us-east-1"
PREFIXE_S3 = "reference/"

_origines: dict = {}   # nom du fichier -> d'où il a été lu


def cle_s3(nom: str) -> str:
    return f"{PREFIXE_S3}{nom}.json"


def _client_s3():
    import boto3
    from botocore.config import Config

    try:
        from agent import identifiants
        identifiants.charger_identifiants()
    except Exception:
        pass
    return boto3.client("s3", region_name=REGION,
                        config=Config(retries={"max_attempts": 2, "mode": "standard"}, connect_timeout=3,
                                      read_timeout=10))


def _lire_local(nom: str) -> dict:
    chemin = DOSSIER_REFERENCE / f"{nom}.json"
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier de référence introuvable : reference/{nom}.json.")
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _raison_echec(e: Exception) -> str:
    code = e.response.get("Error", {}).get("Code", "") if hasattr(e, "response") else ""
    nom = type(e).__name__
    if "NoCredentials" in nom:
        return "identifiants AWS absents"
    if "ExpiredToken" in code or "InvalidAccessKeyId" in code:
        return "identifiants AWS expirés"
    if code in ("NoSuchKey", "404"):
        return "fichier absent du bucket"
    if code in ("NoSuchBucket",):
        return "bucket introuvable"
    if "AccessDenied" in code:
        return "accès refusé"
    return f"S3 injoignable ({code or nom})"


@lru_cache(maxsize=None)
def charger(nom: str) -> dict:
    bucket = configuration.valeur("GLC_BUCKET")
    if bucket:
        try:
            corps = _client_s3().get_object(Bucket=bucket, Key=cle_s3(nom))["Body"].read()
            donnees = json.loads(corps.decode("utf-8"))
            try:
                identique = donnees == _lire_local(nom)
            except FileNotFoundError:
                identique = None
            _origines[nom] = {"lieu": "s3", "identique_au_local": identique}
            return donnees
        except Exception as e:
            _origines[nom] = {"lieu": "local", "repli": True, "raison": _raison_echec(e)}
            return _lire_local(nom)
    _origines[nom] = {"lieu": "local", "repli": False}
    return _lire_local(nom)


def origine() -> dict:
    """D'où les fichiers de référence ont été lus, avec une phrase en français pour le rapport."""
    bucket = configuration.valeur("GLC_BUCKET")
    lus = dict(_origines)
    s3 = sorted(n for n, o in lus.items() if o["lieu"] == "s3")
    replis = {n: o["raison"] for n, o in lus.items() if o.get("repli")}
    differents = sorted(n for n, o in lus.items() if o.get("identique_au_local") is False)
    if s3 and not replis:
        lieu = "s3"
        message = (f"Fichiers de référence lus dans Amazon S3 (bucket privé, chiffré), {len(s3)} fichier(s).")
    elif s3:
        lieu = "mixte"
        message = (f"Fichiers de référence lus dans Amazon S3, sauf {len(replis)} lu(s) dans le dossier local "
                   f"reference/ ({', '.join(sorted(set(replis.values())))}).")
    elif replis:
        lieu = "local"
        message = ("Fichiers de référence lus dans le dossier local reference/ : Amazon S3 n'a pas répondu "
                   f"({', '.join(sorted(set(replis.values())))}).")
    else:
        lieu = "local"
        message = "Fichiers de référence lus dans le dossier local reference/ (bucket S3 non configuré)."
    if differents:
        message += f" Attention : copie S3 différente du dossier local pour {', '.join(differents)}."
    return {"lieu": lieu, "bucket_configure": bool(bucket), "fichiers": lus, "message": message}


def reinitialiser() -> None:
    """Oublie les fichiers déjà lus (essais, ou après un changement de configuration)."""
    charger.cache_clear()
    _origines.clear()


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
