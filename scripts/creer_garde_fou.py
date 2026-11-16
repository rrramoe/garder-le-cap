"""Crée (ou met à jour) le garde-fou Bedrock de Garder le cap, publie une version et exporte sa configuration.

    python scripts/creer_garde_fou.py

Idempotent : si un garde-fou du même nom existe, il est réutilisé ; son brouillon est mis à jour et une
nouvelle version n'est publiée que si la configuration a changé. L'identifiant et la version sont écrits
dans le fichier local `glc.env` (ignoré par git), jamais affichés. La configuration publiée est exportée
dans `docs/configuration/guardrail-config.json`, numéro de compte et identifiant masqués.

Niveau CLASSIC : il prend en charge le français pour les sujets refusés et l'ancrage contextuel, sans
inférence interrégionale. Noms de sujets sans accents ; définitions de 200 caractères au plus.
Les définitions sont en anglais et les exemples en français : à l'essai sur huit phrases, c'est la seule
variante qui refuse les trois demandes visées sans bloquer l'inspection d'un persona fictif (des
définitions en français laissaient passer « dois-je acheter Tesla avec mon REER ? » ; le niveau STANDARD
bloquait la consigne d'inspection elle-même).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import boto3  # noqa: E402

from agent import identifiants  # noqa: E402
from moteur import configuration  # noqa: E402

REGION = identifiants.REGION
NOM = "garder-le-cap-garde-fou"
EXPORT = RACINE / "docs" / "configuration" / "guardrail-config.json"

MESSAGE_ENTREE = ("Demande refusée par le garde-fou : Garder le cap est une simulation éducative. Il ne donne "
                  "aucun conseil financier personnalisé et ne passe aucune transaction réelle.")
MESSAGE_SORTIE = ("Réponse retenue par le garde-fou : elle sortait du cadre de la simulation (conseil "
                  "personnalisé, transaction réelle ou affirmation non appuyée par les résultats des outils).")

SUJETS = [
    {
        "name": "Conseil financier personnalise",
        "definition": ("Requests asking what the user personally should buy, sell or hold, or whether an investment "
                       "is a good idea for them, with their own money or savings; includes asking to be advised."),
        "examples": [
            "Je suis un vrai client : dois-je acheter Tesla avec mon REER ?",
            "Dois-je acheter Tesla avec mes économies ? Conseille-moi.",
            "Est-ce une bonne idée pour moi d'acheter NVDA maintenant ?",
            "Est-ce que je devrais vendre mes actions maintenant ?",
            "Quel placement me conseillez-vous pour ma retraite ?",
        ],
        "type": "DENY",
    },
    {
        "name": "Transaction reelle",
        "definition": ("Requests to execute, place or transmit a real order or trade on a real brokerage account, "
                       "or to move real money."),
        "examples": [
            "Passe cet ordre pour de vrai sur mon compte",
            "Achète 100 actions de Tesla sur mon compte de courtage",
            "Transfère 5000 dollars de mon compte vers mon REER",
        ],
        "type": "DENY",
    },
]

# Seuils de l'ancrage contextuel : une réponse dont le score est sous le seuil est rejetée.
ANCRAGE = [
    {"type": "GROUNDING", "threshold": 0.7},
    {"type": "RELEVANCE", "threshold": 0.5},
]


def configuration_voulue() -> dict:
    return {
        "name": NOM,
        "description": "Garder le cap : refuse le conseil personnalisé et la transaction réelle ; ancrage contextuel.",
        "topicPolicyConfig": {"topicsConfig": SUJETS, "tierConfig": {"tierName": "CLASSIC"}},
        "contextualGroundingPolicyConfig": {"filtersConfig": ANCRAGE},
        "blockedInputMessaging": MESSAGE_ENTREE,
        "blockedOutputsMessaging": MESSAGE_SORTIE,
    }


def _empreinte(g: dict) -> str:
    """Résumé comparable d'une réponse `get_guardrail` (sujets, ancrage, messages)."""
    sujets = sorted((t["name"], t["definition"], tuple(t.get("examples", [])), t["type"])
                    for t in g.get("topicPolicy", {}).get("topics", []))
    ancrage = sorted((f["type"], round(float(f["threshold"]), 3))
                     for f in g.get("contextualGroundingPolicy", {}).get("filters", []))
    return json.dumps([sujets, ancrage, g.get("blockedInputMessaging"), g.get("blockedOutputsMessaging")],
                      ensure_ascii=False)


def _trouver(client) -> dict | None:
    jeton = None
    while True:
        r = client.list_guardrails(**({"nextToken": jeton} if jeton else {}))
        for g in r.get("guardrails", []):
            if g["name"] == NOM:
                return g
        jeton = r.get("nextToken")
        if not jeton:
            return None


def _derniere_version(client, gid: str) -> str | None:
    versions, jeton = [], None
    while True:
        r = client.list_guardrails(guardrailIdentifier=gid, **({"nextToken": jeton} if jeton else {}))
        versions += [g["version"] for g in r.get("guardrails", []) if g["version"] != "DRAFT"]
        jeton = r.get("nextToken")
        if not jeton:
            break
    return max(versions, key=int) if versions else None


def masquer(objet):
    """Masque le numéro de compte (12 chiffres) et l'identifiant du garde-fou dans l'export."""
    texte = json.dumps(objet, ensure_ascii=False, indent=2, default=str)
    gid = objet.get("guardrailId")
    if gid:
        texte = texte.replace(gid, "<identifiant-garde-fou>")
    texte = re.sub(r"(?<!\d)\d{12}(?!\d)", "<compte>", texte)
    return json.loads(texte)


def exporter(client, gid: str, version: str) -> Path:
    g = client.get_guardrail(guardrailIdentifier=gid, guardrailVersion=version)
    g.pop("ResponseMetadata", None)
    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    EXPORT.write_text(json.dumps(masquer(g), ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return EXPORT


def _attendre_pret(client, gid: str, version: str = "DRAFT", essais: int = 30) -> None:
    for _ in range(essais):
        statut = client.get_guardrail(guardrailIdentifier=gid, guardrailVersion=version)["status"]
        if statut == "READY":
            return
        if statut == "FAILED":
            raise RuntimeError("le garde-fou est en échec")
        time.sleep(2)
    raise TimeoutError("le garde-fou n'est pas prêt")


def main() -> int:
    if not identifiants.charger_identifiants():
        print("Identifiants AWS absents : copiez-les dans ~/.aws/datathon.env.")
        return 1
    client = boto3.client("bedrock", region_name=REGION)
    voulue = configuration_voulue()
    try:
        existant = _trouver(client)
        if existant is None:
            gid = client.create_guardrail(**voulue)["guardrailId"]
            print("Garde-fou créé.")
        else:
            gid = existant["id"]
            client.update_guardrail(guardrailIdentifier=gid, **voulue)
            print("Garde-fou existant réutilisé ; brouillon mis à jour.")
        _attendre_pret(client, gid)
        version = _derniere_version(client, gid)
        brouillon = client.get_guardrail(guardrailIdentifier=gid, guardrailVersion="DRAFT")
        publiee = client.get_guardrail(guardrailIdentifier=gid, guardrailVersion=version) if version else None
        if publiee is None or _empreinte(publiee) != _empreinte(brouillon):
            version = client.create_guardrail_version(guardrailIdentifier=gid,
                                                      description="Version publiée pour la démo")["version"]
            _attendre_pret(client, gid, version)
            print(f"Version {version} publiée.")
        else:
            print(f"Configuration inchangée : version {version} conservée.")
        configuration.ecrire_valeurs({"GLC_GARDE_FOU_ID": gid, "GLC_GARDE_FOU_VERSION": version})
        print(f"Identifiant et version écrits dans {configuration.chemin_fichier().name} (non publié).")
        print(f"Configuration exportée : {exporter(client, gid, version).relative_to(RACINE)}")
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else None
        print(f"Échec : {code or type(e).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
