"""Crée le bucket S3 privé des fichiers de référence et y dépose les fichiers de `reference/`.

    python scripts/creer_bucket.py

Idempotent : si `GLC_BUCKET` est déjà configuré (fichier local `glc.env`) et que le bucket existe, il est
réutilisé ; sinon un bucket `garder-le-cap-reference-<suffixe aléatoire>` est créé dans us-east-1.
Dans les deux cas : les quatre blocages d'accès public sont activés, le chiffrement par défaut (SSE-S3)
est imposé, une politique refuse tout accès hors TLS, puis chaque `reference/*.json` est déposé sous
`reference/`. Le nom du bucket est écrit dans `glc.env` (ignoré par git).
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import boto3  # noqa: E402

from agent import identifiants  # noqa: E402
from moteur import configuration, references  # noqa: E402

REGION = identifiants.REGION
PREFIXE_NOM = "garder-le-cap-reference-"
BLOCAGE_PUBLIC = {"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True,
                  "RestrictPublicBuckets": True}


def politique_tls(bucket: str) -> str:
    return json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "RefuserHorsTLS", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})


def _existe(s3, bucket: str) -> bool:
    try:
        s3.head_bucket(Bucket=bucket)
        return True
    except Exception:
        return False


def securiser(s3, bucket: str) -> None:
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration=BLOCAGE_PUBLIC)
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}, "BucketKeyEnabled": True}]})
    s3.put_bucket_policy(Bucket=bucket, Policy=politique_tls(bucket))


def deposer(s3, bucket: str) -> list:
    deposes = []
    for chemin in sorted(references.DOSSIER_REFERENCE.glob("*.json")):
        s3.put_object(Bucket=bucket, Key=references.cle_s3(chemin.stem), Body=chemin.read_bytes(),
                      ContentType="application/json; charset=utf-8")
        deposes.append(chemin.name)
    return deposes


def verifier(s3, bucket: str) -> list:
    """Problèmes de configuration constatés (liste vide si le bucket est privé et chiffré)."""
    problemes = []
    blocage = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    if not all(blocage.get(k) for k in BLOCAGE_PUBLIC):
        problemes.append("blocage de l'accès public incomplet")
    regles = s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"]
    if not regles:
        problemes.append("chiffrement par défaut absent")
    if s3.get_bucket_policy_status(Bucket=bucket)["PolicyStatus"].get("IsPublic"):
        problemes.append("politique publique")
    return problemes


def main() -> int:
    if not identifiants.charger_identifiants():
        print("Identifiants AWS absents : copiez-les dans ~/.aws/datathon.env.")
        return 1
    s3 = boto3.client("s3", region_name=REGION)
    try:
        bucket = configuration.valeur("GLC_BUCKET")
        if bucket and _existe(s3, bucket):
            print("Bucket existant réutilisé.")
        else:
            bucket = PREFIXE_NOM + secrets.token_hex(4)
            s3.create_bucket(Bucket=bucket)  # us-east-1 : pas de LocationConstraint
            s3.get_waiter("bucket_exists").wait(Bucket=bucket)
            print("Bucket créé.")
        securiser(s3, bucket)
        configuration.ecrire_valeurs({"GLC_BUCKET": bucket})
        print(f"{len(deposer(s3, bucket))} fichiers de référence déposés.")
        problemes = verifier(s3, bucket)
        print("Bucket privé, chiffré, accès hors TLS refusé." if not problemes else "Attention : " + ", ".join(problemes))
        print(f"Nom du bucket écrit dans {configuration.chemin_fichier().name} (non publié).")
        return 1 if problemes else 0
    except Exception as e:
        code = e.response.get("Error", {}).get("Code") if hasattr(e, "response") else None
        print(f"Échec : {code or type(e).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
