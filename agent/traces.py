"""Trace de chaque analyse réellement faite, dans l'espace AWS privé du projet.

    preparer(resultat, client, ordre, reglages) -> str | None     # donne l'identifiant, lance l'écriture en fond
    construire(resultat, client, ordre, reglages, identifiant) -> dict

Une analyse faite (pas un rejeu de la mémoire) laisse une trace JSON dans le bucket privé, sous
`traces/<date UTC>/<identifiant>.json`, et une ligne compacte dans Amazon CloudWatch Logs (groupe du réglage
`GLC_JOURNAL_GROUPE`, un flux par jour). L'écriture se fait dans un fil à part, avec des délais courts et sans jamais lever : une trace
qui échoue ne retarde, ne change ni ne casse une analyse, et le visiteur n'en voit rien.

Ce que la trace contient : l'identifiant, l'heure UTC, la version de l'application si elle est connue, une empreinte
de la fiche (jamais son contenu, sauf le profil déduit), l'ordre, les modèles et les réglages, chaque étape dans
l'ordre (le tri et le mandat du chef de dossier, chaque appel d'outil de chaque agent avec ses arguments et la réponse
du moteur, le retour de l'explorateur, le jugement et le renvoi éventuel), les contrôles de l'explication, le
garde-fou, le verdict et l'angle déterminant donnés par le moteur, l'explication, les durées et le repli éventuel.
Aucune adresse de visiteur, aucun identifiant AWS, aucun secret. Les poids du portefeuille sont retirés des réponses
du moteur.

Réglages : `GLC_TRACES` (actif par défaut quand un bucket est configuré, `0` l'éteint ; sans bucket, rien n'est
fait) et `GLC_JOURNAL_GROUPE` (le groupe CloudWatch Logs ; vide, aucune ligne). Droits utilisés, et seuls : s3:PutObject
sous traces/, logs:CreateLogStream et logs:PutLogEvents sur ce groupe.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from moteur import configuration

PREFIXE = "traces/"
def groupe_journal() -> str | None:
    """Le groupe CloudWatch Logs, reçu par le réglage `GLC_JOURNAL_GROUPE` ; vide : aucune ligne envoyée."""
    return configuration.valeur("GLC_JOURNAL_GROUPE")
RACINE = Path(__file__).resolve().parent.parent
# Clés retirées des réponses du moteur : le contenu de la fiche (poids du portefeuille, réponses, nom).
CLES_PRIVEES = {"portefeuille_pct", "portefeuille_avant_pct", "portefeuille_apres_pct", "questionnaire", "nom",
                "poids_par_classe_pct", "sources"}


def actives() -> bool:
    return os.environ.get("GLC_TRACES", "1").strip() != "0" and configuration.valeur("GLC_BUCKET") is not None


def nouvel_identifiant() -> str:
    return secrets.token_urlsafe(12)


def _version_application() -> str | None:
    v = os.environ.get("GLC_VERSION_APPLICATION")
    if v:
        return v.strip()
    try:
        r = subprocess.run(["git", "-C", str(RACINE), "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, timeout=2)
        return r.stdout.strip() or None
    except Exception:
        return None


def _sans_fiche(x):
    """Une réponse du moteur sans le contenu de la fiche du client (poids, réponses, nom)."""
    if isinstance(x, dict):
        return {k: _sans_fiche(v) for k, v in x.items() if k not in CLES_PRIVEES}
    if isinstance(x, list):
        return [_sans_fiche(v) for v in x]
    return x


def empreinte_fiche(fiche: dict) -> str:
    contenu = {k: v for k, v in (fiche or {}).items() if k != "sources"}
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def construire(resultat: dict, fiche: dict, ordre: dict, reglages: dict, identifiant: str) -> dict:
    trace = resultat.get("trace") or []
    agents = resultat.get("agents") or []
    chef = agents[0] if agents else {}
    explorateur = next((a for a in agents if a.get("nom") == "explorateur"), {})
    etapes = []
    for e in trace:
        etape = {"etape": e.get("etape"), "agent": e.get("agent"), "outil": e.get("outil"),
                 "arguments": e.get("arguments"), "resume": e.get("resultat_resume")}
        if e.get("outil") == "lire_fiche_client":
            etape["reponse_du_moteur"] = {"profil_deduit": (((e.get("resultat") or {}).get("deduit") or {})
                                                            .get("profil") or {}).get("valeur"),
                                          "empreinte_fiche": empreinte_fiche(e.get("resultat") or {})}
        else:
            etape["reponse_du_moteur"] = _sans_fiche(e.get("resultat"))
        etapes.append(etape)
    simulation = next((e.get("resultat") for e in trace if e.get("outil") == "simuler_ordre"
                       and e.get("agent") in (None, "principal") and isinstance(e.get("resultat"), dict)), {}) or {}
    ancrage = resultat.get("ancrage") or {}
    return {
        "identifiant": identifiant,
        "heure_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version_application": _version_application(),
        "fiche": {"empreinte": empreinte_fiche(fiche), "profil_deduit": ((fiche.get("deduit") or {}).get("profil")
                                                                        or {}).get("valeur")},
        "ordre": ordre,
        "modele": resultat.get("modele"),
        "reglages": reglages,
        "etapes": etapes,
        "chef_de_dossier": {"mandat": chef.get("mandat"), "jugements": chef.get("jugements"),
                            "mandat_ecrit": explorateur.get("mission")},
        "explorateur": {"statut": explorateur.get("statut"), "avis": explorateur.get("avis"),
                        "bilan": explorateur.get("bilan"), "raison_du_repli": explorateur.get("raison_du_repli")},
        "pistes": _sans_fiche(resultat.get("pistes")),
        "controles": {"chiffres_non_sources": ancrage.get("chiffres_non_sources"), "ancrage": ancrage.get("statut"),
                      "message": ancrage.get("message"), "correction": resultat.get("correction")},
        "garde_fou": resultat.get("garde_fou"),
        "verdict_du_moteur": (simulation.get("verdict") or {}).get("code"),
        "direction_du_moteur": (simulation.get("direction") or {}).get("libelle"),
        "angle_determinant": {"angle": simulation.get("dimension_min"), "mesure": simulation.get("mesure_min")},
        "explication": resultat.get("explication"),
        "duree_s": resultat.get("duree_s"),
        "repli": explorateur.get("statut") == "repli",
        "erreur": resultat.get("erreur"),
    }


def ligne_compacte(trace: dict) -> str:
    a = trace.get("angle_determinant") or {}
    return json.dumps({"id": trace["identifiant"], "verdict": trace.get("verdict_du_moteur"),
                       "angle_determinant": f"{a.get('angle')}/{a.get('mesure')}", "duree_s": trace.get("duree_s"),
                       "modeles": (trace.get("reglages") or {}).get("modeles"), "repli": trace.get("repli")},
                      ensure_ascii=False)


def _clients():
    import boto3
    from botocore.config import Config

    from . import identifiants

    identifiants.charger_identifiants()
    config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})
    return (boto3.client("s3", region_name=identifiants.REGION, config=config),
            boto3.client("logs", region_name=identifiants.REGION, config=config))


def ecrire(trace: dict, s3=None, logs=None) -> dict:
    """Écrit la trace (S3) et sa ligne (CloudWatch Logs). Ne lève jamais ; rend ce qui a réussi."""
    etat = {"s3": False, "logs": False}
    try:
        if s3 is None or logs is None:
            s3_defaut, logs_defaut = _clients()
            s3, logs = s3 or s3_defaut, logs or logs_defaut
    except Exception:
        return etat
    jour = trace["heure_utc"][:10]
    try:
        s3.put_object(Bucket=configuration.valeur("GLC_BUCKET"), Key=f"{PREFIXE}{jour}/{trace['identifiant']}.json",
                      Body=json.dumps(trace, ensure_ascii=False, default=str).encode("utf-8"),
                      ContentType="application/json")
        etat["s3"] = True
    except Exception:
        pass
    groupe = groupe_journal()
    if not groupe:
        return etat
    try:
        # Seuls droits : CreateLogStream et PutLogEvents sur ce groupe. Le flux du jour est créé ; « existe déjà »
        # vaut succès. Ni création de groupe, ni lecture des flux, ni jeton de séquence.
        try:
            logs.create_log_stream(logGroupName=groupe, logStreamName=jour)
        except Exception as e:
            if "ResourceAlreadyExists" not in f"{type(e).__name__} {getattr(e, 'response', '')} {e}":
                raise
        logs.put_log_events(logGroupName=groupe, logStreamName=jour,
                            logEvents=[{"timestamp": int(time.time() * 1000), "message": ligne_compacte(trace)}])
        etat["logs"] = True
    except Exception:
        pass
    return etat


CLIENTS = None        # (s3, logs) imposés par les essais ; sinon créés à l'écriture
ATTENDRE = False      # les essais attendent la fin de l'écriture


def preparer(resultat: dict, fiche: dict, ordre: dict, reglages: dict, s3=None, logs=None, attendre=None) -> str | None:
    """Donne un identifiant à l'analyse et lance l'écriture de sa trace en fond. None si les traces sont éteintes."""
    if not actives():
        return None
    try:
        identifiant = nouvel_identifiant()
        trace = construire(resultat, fiche, ordre, reglages, identifiant)
    except Exception:
        return None
    if CLIENTS is not None and s3 is None and logs is None:
        s3, logs = CLIENTS
    fil = threading.Thread(target=ecrire, args=(trace, s3, logs), name="trace", daemon=True)
    fil.start()
    if attendre if attendre is not None else ATTENDRE:
        fil.join(10)
    return identifiant
