"""Agent explorateur : envoyé par le chef de dossier pour un ordre « en tension », il cherche et teste des pistes.

    explorer(client, ordre, mission, simulation, modele=None, sur_etape=None, compteur=None) -> dict

Le code fixe ce qui est une règle : l'en-tête des faits (ordre, résultat du moteur, cause, portefeuille, thèmes),
les outils et leur borne de quatre pistes, la limite de tours, le délai, et le repli sur la taille compatible
calculée par le code si l'explorateur échoue. Ne lève jamais d'exception.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as DelaiDepasse
from pathlib import Path

from moteur import api

from .outils import LIMITE_PISTES, creer_outils_explorateur, identifiant_client
from .suivi import Suivi

PROMPT_EXPLORATEUR = Path(__file__).parent / "prompts" / "explorateur.md"
LIMITE_TOURS_EXPLORATEUR = 10    # 2 lectures, jusqu'à 6 essais (souvent deux par tour), le compte rendu
DELAI_EXPLORATEUR_S = 150
AVIS_REPLI = ("L'explorateur n'a pas pu finir : seule la taille compatible calculée par le code est montrée.")


def _theme_lisible(themes: dict) -> dict:
    return {k: v for k, v in (themes or {}).items() if v != "neutre"}


def entete(client, ordre: dict, mission: str, simulation: dict) -> str:
    """Message de l'explorateur : les faits écrits par le code, puis la mission écrite par le chef de dossier."""
    fiche = api.lire_fiche_client(client)
    op = ordre.get("operation") or "comptant"
    faits = {
        "client_id": identifiant_client(client),
        "ordre": {k: ordre[k] for k in ("ticker", "sens", "pourcentage")} | ({"operation": op} if op != "comptant" else {}),
        "resultat_de_l_ordre": {"verdict": simulation.get("verdict", {}).get("code"), "score": simulation.get("score"),
                                "direction": simulation.get("direction", {}).get("cas"),
                                "cause": simulation.get("cause")},
        "portefeuille_pct": fiche.get("portefeuille_pct"),
        "poids_par_classe_pct": fiche.get("poids_par_classe_pct"),
        "themes_du_client": _theme_lisible((fiche.get("questionnaire") or {}).get("themes")),
        "objectif": (fiche.get("questionnaire") or {}).get("objectif"),
    }
    return ("Faits établis par le code (ne les recalcule pas) :\n" + json.dumps(faits, ensure_ascii=False) +
            "\n\nMission du chef de dossier :\n" + (mission or "(aucune précision)") +
            "\n\nCherche et teste les pistes, puis rends ton compte rendu en trois lignes.")


def lire_compte_rendu(texte: str | None) -> dict:
    """Les lignes du compte rendu : `intention` (la finalité supposée), `cause`, `retenues` (numéros d'essai) et
    `bilan` ; une ligne absente vaut None."""
    resultat = {"intention": None, "cause": None, "retenues": None, "bilan": None}
    for cle, nom in (("intention", r"(?:Finalit[ée] suppos[ée]e|Intention)"), ("cause", "Cause"),
                     ("retenues", r"Pistes retenues"), ("bilan", "Bilan")):
        m = re.search(rf"^[\W_]*{nom}[\W_]*:\s*(.+)$", texte or "", flags=re.MULTILINE | re.IGNORECASE)
        if m:
            resultat[cle] = m.group(1).strip().strip("*").strip()
    if resultat["retenues"] is not None:
        resultat["retenues"] = [int(n) for n in re.findall(r"\d+", resultat["retenues"])]
    return resultat


def retenir(pistes_et_essais: list, retenues: list | None, limite: int = LIMITE_PISTES) -> list:
    """Les pistes que l'explorateur garde, quatre au plus. Sans choix lisible : les quatre dernières testées."""
    if retenues:
        choix = [p for n, p in pistes_et_essais if n in retenues][:limite]
        if choix:
            return choix
    return [p for _, p in pistes_et_essais][-limite:]


def _pistes_pour_le_chef(pistes: list) -> list:
    return [{"famille": p["libelle_famille"], "piste": p["description"], "raison": p.get("raison"),
             "ordres": p.get("ordres"),
             "verdict": (p.get("verdict") or {}).get("libelle"), "score": p.get("score"),
             "direction": (p.get("direction") or {}).get("libelle")} for p in pistes]


def repli(client, ordre: dict, simulation: dict, raison: str) -> dict:
    """Sans explorateur : la taille compatible calculée par le code, présentée comme une piste."""
    from .inspection import extraire_pistes

    op = ordre.get("operation") or "comptant"
    taille = api.chercher_taille_compatible(client, ordre["ticker"], ordre["sens"], ordre["pourcentage"], op)
    trace = [{"etape": 0, "outil": "simuler_ordre", "arguments": {}, "resultat": simulation},
             {"etape": 0, "outil": "chercher_taille_compatible",
              "arguments": {"raison": "Calculée par le code : l'explorateur n'a pas pu finir."}, "resultat": taille}]
    pistes = [dict(p, etape=None) for p in extraire_pistes(trace, ordre["ticker"], ordre["sens"], ordre["pourcentage"])]
    return {"statut": "repli", "avis": AVIS_REPLI, "raison_du_repli": raison, "intention": None, "cause_lue": None,
            "bilan": None, "cause": simulation.get("cause"), "pistes": pistes, "trace": [], "taille": taille,
            "retour": {"statut": "repli", "avis": AVIS_REPLI, "cause": simulation.get("cause"),
                       "pistes": _pistes_pour_le_chef(pistes)}}


def explorer(client, ordre: dict, mission: str, simulation: dict, modele=None, sur_etape=None, compteur=None,
             delai_s: float | None = None) -> dict:
    """Fait travailler l'explorateur. Renvoie `statut` (`termine` ou `repli`), `intention`, `cause_lue`, `bilan`,
    `cause` (du moteur), `pistes` (construites par le code), `trace` (ses étapes) et `retour` (ce que lit le chef)."""
    from strands import Agent, ModelRetryStrategy

    from .inspection import creer_modele, extraire_pistes, extraire_trace, nom_modele, texte_final
    from . import identifiants

    delai_s = DELAI_EXPLORATEUR_S if delai_s is None else delai_s
    suivi = Suivi(sur_etape, agent="explorateur", ticker_ordre=ordre["ticker"], compteur=compteur)
    etat = {"agent": None}

    def travailler():
        m = modele
        if m is None or isinstance(m, str):
            identifiants.charger_identifiants()
            m = creer_modele(nom_modele(m))
        agent = Agent(model=m, tools=creer_outils_explorateur(client),
                      system_prompt=PROMPT_EXPLORATEUR.read_text(encoding="utf-8"), callback_handler=suivi.rappel,
                      hooks=[suivi], name="explorateur",
                      retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=16))
        etat["agent"] = agent
        return agent(entete(client, ordre, mission, simulation), limits={"turns": LIMITE_TOURS_EXPLORATEUR})

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="explorateur")
    try:
        resultat = pool.submit(travailler).result(timeout=delai_s)
    except DelaiDepasse:
        suivi.sur_etape = None     # l'explorateur abandonné ne parle plus à l'interface
        return repli(client, ordre, simulation, f"délai de {int(delai_s)} s dépassé")
    except Exception as e:
        from .inspection import message_erreur
        return repli(client, ordre, simulation, message_erreur(e))
    finally:
        pool.shutdown(wait=False)
    try:
        trace = extraire_trace(etat["agent"].messages) if etat["agent"] is not None else []
        texte = texte_final(getattr(resultat, "message", None))
        cr = lire_compte_rendu(texte)
        trace_complete = [{"etape": 0, "outil": "simuler_ordre", "arguments": {}, "resultat": simulation}] + trace
        essais = {e["etape"]: (e.get("resultat") or {}).get("essai") for e in trace if isinstance(e.get("resultat"), dict)}
        testees = extraire_pistes(trace_complete, ordre["ticker"], ordre["sens"], ordre["pourcentage"])
        pistes = retenir([(essais.get(p["etape"]), p) for p in testees], cr["retenues"])
    except Exception as e:
        return repli(client, ordre, simulation, f"compte rendu illisible ({type(e).__name__})")
    if not pistes:
        return repli(client, ordre, simulation, "aucune piste testée")
    return {"statut": "termine", "intention": cr["intention"], "cause_lue": cr["cause"], "bilan": cr["bilan"],
            "cause": simulation.get("cause"), "pistes": pistes, "nombre_essais": len(testees), "trace": trace,
            "compte_rendu": texte,
            "retour": {"statut": "termine", "finalite_supposee": cr["intention"], "cause_lue": cr["cause"],
                       "bilan": cr["bilan"], "cause": simulation.get("cause"),
                       "pistes": _pistes_pour_le_chef(pistes)}}
