"""Vérification AWS (section 3) : identité, puis un appel `converse` à chacun des deux modèles.

    python scripts/verifier_aws.py

Chaque modèle doit répondre « prêt ». N'affiche aucun identifiant ; en cas d'échec, seulement
le nom de l'erreur (par exemple ExpiredToken ou AccessDeniedException).
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402
from botocore.config import Config  # noqa: E402

from agent import identifiants  # noqa: E402

REGION = identifiants.REGION
MODELES = {"global.amazon.nova-2-lite-v1:0": 200, "global.anthropic.claude-sonnet-5": 1200}
CONSIGNE = "Répondez exactement : prêt"


def _nom_erreur(e: Exception) -> str:
    reponse = getattr(e, "response", None)
    if isinstance(reponse, dict) and reponse.get("Error", {}).get("Code"):
        return reponse["Error"]["Code"]
    return type(e).__name__


def _premier_mot(texte: str) -> str:
    """Premier mot, sans accents ni ponctuation : « Prêt ! ... » donne « pret »."""
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    mots = "".join(c if c.isalpha() else " " for c in texte).split()
    return mots[0] if mots else ""


def main() -> int:
    identifiants.charger_identifiants()
    ok = True
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
        print("Identité AWS : confirmée")
    except Exception as e:
        print(f"Identité AWS : échec ({_nom_erreur(e)})")
        return 1
    bedrock = boto3.client("bedrock-runtime", region_name=REGION,
                           config=Config(retries={"max_attempts": 4, "mode": "adaptive"}))
    for modele, jetons in MODELES.items():
        try:
            r = bedrock.converse(modelId=modele, messages=[{"role": "user", "content": [{"text": CONSIGNE}]}],
                                 inferenceConfig={"maxTokens": jetons})
            texte = "".join(b["text"] for b in r["output"]["message"]["content"] if "text" in b).strip()
            pret = _premier_mot(texte) == "pret"
            ok &= pret
            print(f"{modele} : {'prêt' if pret else 'réponse inattendue'} (« {texte} »)")
        except Exception as e:
            ok = False
            print(f"{modele} : échec ({_nom_erreur(e)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
