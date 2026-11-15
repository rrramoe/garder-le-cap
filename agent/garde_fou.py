"""Garde-fou Bedrock : refus du conseil personnalisé et de la transaction réelle, ancrage contextuel.

    configuration_garde_fou() -> {"id", "version"} ou None
    verifier_ancrage(explication, trace, requete) -> dict
    essayer_garde_fou(texte) -> dict

Le garde-fou est créé par `scripts/creer_garde_fou.py` ; son identifiant et sa version viennent des
variables `GLC_GARDE_FOU_ID` et `GLC_GARDE_FOU_VERSION` (fichier local `glc.env`). Sans elles, rien
n'est appelé et chaque fonction renvoie un statut `non_configure` avec un avis en français.
Aucune fonction ne lève d'exception. Les scores d'ancrage viennent du garde-fou, pas du modèle.
"""
from __future__ import annotations

import json
import re

from moteur import configuration

from . import identifiants

REGION = identifiants.REGION
LIMITE_SOURCE = 95_000      # l'ancrage contextuel accepte 100 000 caractères de source au plus
LIMITE_REQUETE = 1_000
LIMITE_REPONSE = 5_000

AVIS_NON_CONFIGURE = ("Garde-fou Bedrock non configuré : l'explication n'a pas été vérifiée "
                      "(lancez scripts/creer_garde_fou.py).")


def configuration_garde_fou() -> dict | None:
    gid = configuration.valeur("GLC_GARDE_FOU_ID")
    version = configuration.valeur("GLC_GARDE_FOU_VERSION")
    return {"id": gid, "version": version} if gid and version else None


def _client(service: str):
    import boto3
    from botocore.config import Config

    identifiants.charger_identifiants()
    return boto3.client(service, region_name=REGION,
                        config=Config(retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=60,
                                      connect_timeout=10))


def _message_erreur(e: Exception) -> str:
    from .inspection import message_erreur
    return message_erreur(e)


# --- Source d'ancrage ---------------------------------------------------------------------------

def _alleger(valeur):
    """Retire d'un résultat d'outil les longues listes sans intérêt pour l'explication."""
    if isinstance(valeur, dict):
        return {k: _alleger(v) for k, v in valeur.items() if k not in ("instruments",)}
    if isinstance(valeur, list):
        return [_alleger(v) for v in valeur]
    return valeur


def source_ancrage(trace: list) -> str:
    """Texte de référence de l'ancrage : résumé (calculé par le code) puis résultat de chaque outil."""
    morceaux = []
    for e in trace or []:
        morceaux.append(f"Outil {e.get('outil')} ({json.dumps(e.get('arguments') or {}, ensure_ascii=False)}) : "
                        f"{e.get('resultat_resume')}")
    for e in trace or []:
        morceaux.append(f"Résultat complet de {e.get('outil')} : "
                        + json.dumps(_alleger(e.get("resultat")), ensure_ascii=False, separators=(",", ":")))
    texte = "\n".join(morceaux)
    return texte[:LIMITE_SOURCE]


# --- Chiffres de l'explication -----------------------------------------------------------------

_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NOMBRE = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?![\w])")


def _valeurs(objet, sortie: set) -> set:
    """Tous les nombres d'un résultat d'outil, y compris ceux écrits dans les textes (dates, libellés)."""
    if isinstance(objet, bool) or objet is None:
        return sortie
    if isinstance(objet, (int, float)):
        sortie.add(abs(float(objet)))
    elif isinstance(objet, str):
        for n in re.findall(r"\d+(?:[.,]\d+)?", objet):
            sortie.add(float(n.replace(",", ".")))
    elif isinstance(objet, dict):
        for k, v in objet.items():
            _valeurs(k, sortie)
            _valeurs(v, sortie)
    elif isinstance(objet, (list, tuple)):
        for v in objet:
            _valeurs(v, sortie)
    return sortie


def chiffres_non_sources(texte: str, trace: list) -> list:
    """Chiffres du texte qui ne figurent dans aucun résultat d'outil, tels que le code les affiche.

    Un chiffre écrit avec d décimales est accepté s'il est égal à une valeur d'un outil (ou à une fraction
    × 100) mise en forme avec d décimales par Python, comme le fait le rapport (56,25 s'affiche 56,2).
    Le signe est ignoré ; les dates AAAA-MM-JJ sont acceptées si leurs nombres viennent des outils.
    """
    valeurs = set()
    for e in trace or []:
        _valeurs(e.get("resultat"), valeurs)
        _valeurs(e.get("arguments"), valeurs)
    formes = {}
    absents = []
    for jeton in _NOMBRE.findall(_DATE.sub(lambda m: m.group(0).replace("-", " "), texte or "")):
        decimales = len(jeton.replace(",", ".").partition(".")[2])
        if decimales not in formes:
            formes[decimales] = {f"{v:.{decimales}f}" for v in valeurs} | {f"{v * 100:.{decimales}f}" for v in valeurs}
        if jeton.replace(",", ".") not in formes[decimales] and jeton not in absents:
            absents.append(jeton)
    return absents


# --- Ancrage contextuel -------------------------------------------------------------------------

def _filtres_ancrage(reponse: dict) -> dict:
    filtres = {}
    for evaluation in reponse.get("assessments", []):
        for f in evaluation.get("contextualGroundingPolicy", {}).get("filters", []):
            filtres[f.get("type")] = f
    return filtres


def verifier_ancrage(explication: str | None, trace: list, requete: str, client=None,
                     utiliser_garde_fou: bool = True) -> dict:
    """L'explication est-elle appuyée par les résultats des outils ? (ancrage contextuel du garde-fou)

    Deux vérifications : le code contrôle que chaque chiffre de l'explication figure dans un résultat d'outil
    (`chiffres_non_sources`), puis le garde-fou Bedrock mesure l'ancrage contextuel du texte.
    Renvoie `statut` = `appuyee`, `non_appuyee`, `non_configure`, `indisponible` ou `sans_objet`, un
    `message` en français, et les scores et seuils du garde-fou (`ancrage`, `pertinence`).
    """
    if not explication:
        return {"statut": "sans_objet", "message": "Aucune explication à vérifier."}
    absents = chiffres_non_sources(explication, trace)
    resultat = (_ancrage_garde_fou(explication, trace, requete, client) if utiliser_garde_fou else
                {"statut": "non_configure", "message": "Garde-fou Bedrock non appliqué (modèle simulé)."})
    resultat["chiffres_non_sources"] = absents
    if absents:
        resultat["statut"] = "non_appuyee"
        resultat["message"] = ("Chiffre(s) de l'explication qui ne correspondent à aucun résultat des outils tel "
                               f"que le rapport l'affiche : {', '.join(absents)}. Fiez-vous aux chiffres du moteur.")
    elif resultat["statut"] in ("non_configure", "indisponible"):
        resultat["message"] += " Tous les chiffres de l'explication figurent dans les résultats des outils."
    return resultat


def sections(texte: str) -> list:
    """Paragraphes de l'explication (séparés par une ligne vide), titres seuls écartés."""
    morceaux = [m.strip() for m in re.split(r"\n\s*\n", texte or "") if m.strip()]
    return [m for m in morceaux if not re.fullmatch(r"#+ .*", m)] or morceaux


def _evaluer_section(client, config: dict, source: str, requete: str, section: str) -> dict:
    reponse = client.apply_guardrail(
        guardrailIdentifier=config["id"], guardrailVersion=config["version"], source="OUTPUT", outputScope="FULL",
        content=[
            {"text": {"text": source, "qualifiers": ["grounding_source"]}},
            {"text": {"text": requete[:LIMITE_REQUETE], "qualifiers": ["query"]}},
            {"text": {"text": section[:LIMITE_REPONSE], "qualifiers": ["guard_content"]}},
        ])
    return _filtres_ancrage(reponse)


def _ancrage_garde_fou(explication: str, trace: list, requete: str, client=None) -> dict:
    """Ancrage contextuel de chaque paragraphe ; l'explication vaut son paragraphe le moins appuyé.

    Évalué paragraphe par paragraphe : sur un texte entier, un chiffre faux noyé parmi des phrases justes
    déplace à peine le score ; par paragraphe, le score est plus stable et plus sensible.
    """
    config = configuration_garde_fou()
    if config is None:
        return {"statut": "non_configure", "message": AVIS_NON_CONFIGURE}
    from concurrent.futures import ThreadPoolExecutor

    morceaux = sections(explication)
    source = source_ancrage(trace)
    try:
        client = client or _client("bedrock-runtime")
        with ThreadPoolExecutor(max_workers=4) as pool:
            evaluations = list(pool.map(lambda m: _evaluer_section(client, config, source, requete, m), morceaux))
    except Exception as e:
        return {"statut": "indisponible", "message": f"Vérification de l'ancrage impossible : {_message_erreur(e)}"}
    if not evaluations or any(e.get("GROUNDING") is None for e in evaluations):
        return {"statut": "indisponible", "message": "Le garde-fou n'a pas renvoyé d'évaluation de l'ancrage."}
    faible = min(range(len(evaluations)), key=lambda i: evaluations[i]["GROUNDING"].get("score", 0))
    ancrage = evaluations[faible]["GROUNDING"]
    pertinence = min((e["RELEVANCE"] for e in evaluations if e.get("RELEVANCE")),
                     key=lambda f: f.get("score", 0), default=None)
    rejete = any(f.get("action") == "BLOCKED" and f.get("detected", True) for e in evaluations for f in e.values())
    resultat = {
        "statut": "non_appuyee" if rejete else "appuyee",
        "ancrage": {"score": ancrage.get("score"), "seuil": ancrage.get("threshold")},
        "pertinence": {"score": pertinence.get("score"), "seuil": pertinence.get("threshold")} if pertinence else None,
        "paragraphes": [{"debut": m[:60], "score_ancrage": e["GROUNDING"].get("score")}
                        for m, e in zip(morceaux, evaluations)],
        "version_garde_fou": config["version"],
    }
    if rejete:
        resultat["message"] = ("Le garde-fou Bedrock n'a pas trouvé l'appui d'un passage de cette explication dans "
                               f"les résultats des outils (« {morceaux[faible][:60]}… ») : fiez-vous aux chiffres "
                               "du moteur.")
    else:
        resultat["message"] = ("Explication vérifiée par le garde-fou Bedrock : chaque paragraphe est appuyé par les "
                               "résultats des outils de cette inspection.")
    return resultat


# --- Essai du garde-fou -------------------------------------------------------------------------

SUJETS_FR = {
    "Conseil financier personnalise": "conseil financier personnalisé sur votre situation réelle",
    "Transaction reelle": "demande de transaction réelle",
}
AVIS_ESSAI = ("Aucune réponse n'est produite : Garder le cap n'est pas un agent conversationnel, il montre un "
              "rapport d'inspection. Cet essai montre seulement ce que le garde-fou laisse passer.")


def essayer_garde_fou(texte: str, client=None) -> dict:
    """Soumet un texte au seul garde-fou (ApplyGuardrail, en entrée) ; aucun modèle n'y répond.

    Renvoie `statut` = `refuse`, `accepte`, `non_configure`, `indisponible` ou `vide`, un `message`,
    les `sujets` refusés (libellés en français) et l'`avis` qui rappelle qu'aucune réponse n'est produite.
    """
    texte = (texte or "").strip()
    if not texte:
        return {"statut": "vide", "message": "Écrivez une demande à soumettre au garde-fou.", "sujets": []}
    config = configuration_garde_fou()
    if config is None:
        return {"statut": "non_configure", "sujets": [],
                "message": "Garde-fou Bedrock non configuré : l'essai est indisponible."}
    try:
        client = client or _client("bedrock-runtime")
        reponse = client.apply_guardrail(guardrailIdentifier=config["id"], guardrailVersion=config["version"],
                                         source="INPUT", outputScope="FULL",
                                         content=[{"text": {"text": texte[:LIMITE_REPONSE]}}])
    except Exception as e:
        return {"statut": "indisponible", "sujets": [], "message": f"Essai impossible : {_message_erreur(e)}"}
    sujets = [t.get("name") for a in reponse.get("assessments", [])
              for t in a.get("topicPolicy", {}).get("topics", []) if t.get("action") == "BLOCKED"]
    libelles = [SUJETS_FR.get(n, n) for n in dict.fromkeys(sujets)]
    if reponse.get("action") == "GUARDRAIL_INTERVENED":
        detecte = f" Sujet détecté par le garde-fou : {' ; '.join(libelles)}." if libelles else ""
        return {"statut": "refuse", "sujets": libelles, "avis": AVIS_ESSAI, "version_garde_fou": config["version"],
                "message": ("Demande refusée par le garde-fou : il refuse le conseil financier personnalisé et les "
                            "transactions réelles." + detecte),
                "texte_garde_fou": "".join(o.get("text", "") for o in reponse.get("outputs", []))}
    return {"statut": "accepte", "sujets": [], "avis": AVIS_ESSAI, "version_garde_fou": config["version"],
            "message": "Demande acceptée par le garde-fou."}
