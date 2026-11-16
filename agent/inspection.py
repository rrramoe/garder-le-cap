"""Point d'entrée de l'agent d'inspection (Strands Agents sur Amazon Bedrock).

    inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant") -> dict

renvoie toujours `explication`, `trace`, `modele`, `duree_s`, `erreur`, `garde_fou` (état du garde-fou
Bedrock pendant l'inspection), `ancrage` (vérification de l'explication par les résultats des outils) et
`substitut` (l'instrument testé par l'agent à la place de celui de l'ordre, ou None),
sans jamais lever d'exception. Démo sans interface : `python -m agent.inspection robert TSLA achat 15`.
"""
from __future__ import annotations

import json
import re
import os
import sys
import time
from pathlib import Path

from . import garde_fou as _garde_fou
from . import identifiants
from .outils import creer_outils, creer_outils_principal, identifiant_client
from .suivi import Compteur, Suivi
from . import explorateur as _explorateur
from moteur import api as _api_moteur

MODELE_DEFAUT = "global.anthropic.claude-sonnet-5"
REGION = identifiants.REGION
JETONS_SORTIE = 4000          # le bloc de raisonnement compte dans les jetons de sortie
LIMITE_TOURS = 10            # agent seul : 7 tours dans le chemin le plus long (substitut compris), avec une marge
LIMITE_TOURS_PRINCIPAL = 8   # équipe : 3 lectures, l'envoi de l'explorateur, le rapport, avec une marge
# Équipe de deux agents (chef de dossier + explorateur). GLC_EQUIPE=0 revient à l'agent seul d'avant.
EQUIPE = os.environ.get("GLC_EQUIPE", "1").strip() != "0"
# Le chef de dossier décide s'il faut chercher (ordre incompatible compris) et juge les pistes, avec un renvoi au plus.
# GLC_CHEF=0 revient à l'équipe d'avant (envoi pour un ordre en tension seulement, sans jugement des pistes).
CHEF = os.environ.get("GLC_CHEF", "1").strip() != "0"
BUDGET_ANALYSE_S = 60          # la recherche complémentaire du chef tient dans ce budget de toute l'analyse
TEMPS_REDACTION_S = 10         # gardés pour la rédaction et la vérification
MINIMUM_SECOND_TOUR_S = 12     # en dessous, pas de second tour
# Profondeur de raisonnement (output_config.effort) : « medium » garde les preuves de l'équipe et divise le temps
# de chaque tour ; GLC_EFFORT=high revient au défaut du modèle.
EFFORT = os.environ.get("GLC_EFFORT", "medium").strip() or None
# L'explorateur cherche sous un mandat déjà écrit : un effort plus bas suffit et raccourcit ses tours.
EFFORT_EXPLORATEUR = os.environ.get("GLC_EFFORT_EXPLORATEUR", "low").strip() or None
TENTATIVES_SDK = {"max_attempts": 4, "mode": "adaptive"}   # mode de tentatives de botocore (ThrottlingException)
PROMPT_SYSTEME = Path(__file__).parent / "prompts" / "systeme.md"        # agent seul
PROMPT_PRINCIPAL = Path(__file__).parent / "prompts" / "principal.md"    # chef de dossier de l'équipe
PROMPT_CHEF = Path(__file__).parent / "prompts" / "principal_chef.md"   # le même, qui trie et juge (CHEF)


def nom_modele(modele=None) -> str:
    if modele is None or isinstance(modele, str):
        return modele or os.environ.get("GLC_MODELE") or MODELE_DEFAUT
    config = modele.get_config() if hasattr(modele, "get_config") else {}
    return (config or {}).get("model_id") or type(modele).__name__


def options_garde_fou() -> dict:
    """Options Strands qui font porter le garde-fou Bedrock par chaque appel au modèle, s'il est configuré.

    Seul le dernier message texte de l'utilisateur (la consigne) est évalué en entrée ; chaque réponse du
    modèle est évaluée en sortie.
    """
    config = _garde_fou.configuration_garde_fou()
    if config is None:
        return {}
    return {"guardrail_id": config["id"], "guardrail_version": config["version"], "guardrail_trace": "enabled",
            "guardrail_latest_message": True}


def creer_modele(model_id: str, effort: str | None = None, garde_fou: bool = True):
    from botocore.config import Config
    from strands.models import BedrockModel

    effort = EFFORT if effort is None else effort
    extra = {"additional_request_fields": {"output_config": {"effort": effort}}} if effort and effort != "high" else {}
    if garde_fou:
        extra.update(options_garde_fou())
    return BedrockModel(model_id=model_id, region_name=REGION, max_tokens=JETONS_SORTIE, **extra,
                        boto_client_config=Config(retries=TENTATIVES_SDK, read_timeout=120, connect_timeout=10))


def creer_agent(client, modele=None, suivi=None, envoyer=None, juger=None):
    """Agent Strands d'une analyse. `modele` : identifiant Bedrock, ou objet modèle Strands (essais).

    `suivi` : un `agent.suivi.Suivi` qui relaie les étapes en direct, ou None. `envoyer` : la fonction qui fait
    travailler l'explorateur ; donnée, l'agent est le chef de dossier de l'équipe, sinon l'agent seul d'avant.
    """
    from strands import Agent, ModelRetryStrategy

    if modele is None or isinstance(modele, str):
        identifiants.charger_identifiants()
        modele = creer_modele(nom_modele(modele))
    if envoyer is None:
        outils, prompt = creer_outils(client), PROMPT_SYSTEME
    else:
        outils = creer_outils_principal(client, envoyer, juger)
        prompt = PROMPT_CHEF if juger is not None else PROMPT_PRINCIPAL
    return Agent(model=modele, tools=outils, system_prompt=prompt.read_text(encoding="utf-8"),
                 callback_handler=suivi.rappel if suivi is not None else None,
                 name="principal" if envoyer is not None else "inspection",
                 hooks=[suivi] if suivi is not None else None,
                 retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=16))


LIBELLES_OPERATIONS = {"marge": "achat sur marge", "decouvert": "vente à découvert"}


def consigne(client_id: str, ticker: str, sens: str, pourcentage, operation: str = "comptant") -> str:
    ordre = f"Ordre simulé : {sens} de {pourcentage} % du portefeuille en {ticker}.\n"
    if operation != "comptant":
        ordre = (f"Ordre simulé : {LIBELLES_OPERATIONS.get(operation, operation)} ({sens}) de {pourcentage} % du "
                 f"portefeuille en {ticker}, operation=\"{operation}\".\n")
    return (f"Analyse demandée.\nClient : client_id=\"{client_id}\".\n" + ordre +
            "Monte le dossier avec les outils, puis rédige le rapport.")


# --- Lecture de la réponse et de la trace -------------------------------------------------------

def texte_final(message) -> str | None:
    """Concatène les blocs `text` du message final ; le bloc de raisonnement est écarté."""
    if not message:
        return None
    morceaux = [b["text"] for b in message.get("content", []) if isinstance(b, dict) and b.get("text")]
    texte = "".join(morceaux).strip()
    return texte or None


def _contenu_resultat(resultat_outil):
    if resultat_outil is None:
        return None
    valeurs = []
    for bloc in resultat_outil.get("content", []):
        if "json" in bloc:
            valeurs.append(bloc["json"])
        elif "text" in bloc:
            try:
                valeurs.append(json.loads(bloc["text"]))
            except (TypeError, ValueError):
                valeurs.append(bloc["text"])
    valeur = valeurs[0] if len(valeurs) == 1 else (valeurs or None)
    if resultat_outil.get("status") == "error" and not (isinstance(valeur, dict) and "erreur" in valeur):
        return {"erreur": valeur if isinstance(valeur, str) else json.dumps(valeur, ensure_ascii=False)}
    return valeur


def _nombre(x, decimales=1) -> str:
    try:
        return f"{float(x):.{decimales}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def _pct(fraction) -> str:
    try:
        return f"{_nombre(float(fraction) * 100)} %"
    except (TypeError, ValueError):
        return str(fraction)


ETIQUETTES = {"speculatif": "spéculatif", "etablie": "établie", "crypto": "cryptoactif", "techno": "technologie",
              "ecarte_esg": "écarté ESG", "devise_etrangere": "devise étrangère",
              "action_individuelle": "action individuelle", "dividende": "dividende"}


def _etiquette(e) -> str:
    """Nom lisible d'une étiquette ou d'un thème, quel qu'il soit (jamais l'identifiant avec un tiret bas)."""
    return ETIQUETTES.get(e, str(e).replace("_", " "))
NIVEAUX = {"essentiel": "essentiel", "standard": "standard", "detaille": "détaillé"}
DIMENSIONS = {"risque": "risque", "diversification": "diversification", "preferences": "préférences",
              "objectif": "objectif", "liquidite": "liquidité", "liquidites": "liquidité"}
MESURES = {"ampleur": "ampleur de la pire baisse", "duree": "durée sous l'eau", "classe_liquidites": "poids des liquidités",
           "classe_revenu_fixe": "poids du revenu fixe", "classe_actions": "poids des actions",
           "classe_alternatifs": "poids des titres alternatifs", "crypto": "poids des cryptoactifs",
           "plus_grosse_action": "plus grosse action", "plus_gros_fonds": "plus gros fonds",
           "plus_gros_secteur": "plus gros secteur", "fluctuations": "fluctuations", "pire_annee": "pire année",
           "capital_preserve": "capital préservé sur l'horizon", "revenu": "revenu du portefeuille",
           "actions": "poids des actions", "liquidites_besoin": "liquidités face au besoin",
           "geographie_actions": "répartition géographique des actions"}
ISSUES = {"compatible_tel_quel": "compatible tel quel", "compatible_avec_ajustement": "compatible avec ajustement",
          "aucune_taille": "aucune taille"}
CLASSES = {"liquidites": "liquidités", "revenu_fixe": "revenu fixe", "actions": "actions",
           "alternatifs": "titres alternatifs", "toutes": "toutes"}


def libelle_famille(r: dict, d) -> str:
    """Nom lisible d'une famille de notes : le libellé que le moteur donne, sinon le tableau, sinon l'identifiant."""
    note = ((r.get("apres") or r).get("notes") or {}).get(d) if isinstance(r, dict) else None
    if isinstance(note, dict) and isinstance(note.get("libelle_court"), str):
        return note["libelle_court"]
    return DIMENSIONS.get(d, str(d).replace("_", " "))


def _mesure(m) -> str:
    if isinstance(m, str) and m.startswith("theme_"):
        return f"thème « {ETIQUETTES.get(m[len('theme_'):], m[len('theme_'):])} »"
    return MESURES.get(m, _etiquette(m))


def resumer(outil: str, r) -> str:
    """Résumé d'une ligne, en français, du résultat d'un outil (chiffres recopiés du moteur)."""
    try:
        if r is None:
            return "Aucun résultat (appel interrompu)."
        if not isinstance(r, dict):
            return str(r)[:200]
        if "erreur" in r:
            return f"Erreur : {r['erreur']}"
        if outil == "lire_fiche_client":
            d = r.get("deduit", {})
            contraintes = d.get("contraintes_strictes", {}).get("valeur") or []
            noms = ", ".join(_etiquette(n) for n in (c.get("theme", str(c)) if isinstance(c, dict) else str(c)
                                                            for c in contraintes))
            return (f"{r.get('nom')} : profil {d.get('profil', {}).get('libelle') or d.get('profil', {}).get('valeur')}, "
                    f"horizon {d.get('horizon_annees', {}).get('valeur')} ans, "
                    f"contraintes strictes : {noms or 'aucune'}, "
                    f"détail {NIVEAUX.get(d.get('niveau_detail', {}).get('valeur'), d.get('niveau_detail', {}).get('valeur'))}.")
        if outil == "lire_fiche_instrument":
            s = r.get("statistiques_cad", {})
            et = r.get("etiquettes", {})
            vraies = [_etiquette(k) for k, v in et.items() if v.get("valeur") is True]
            indet = [_etiquette(k) for k, v in et.items() if v.get("valeur") == "indetermine"]
            texte = (f"{r.get('nom')} ({CLASSES.get(r.get('classe_politique'), r.get('classe_politique'))}, "
                     f"{r.get('devise')}) : volatilité "
                     f"{_pct(s.get('volatilite_annualisee'))}, pire baisse {_pct(s.get('pire_baisse'))} ; "
                     f"étiquettes : {', '.join(vraies) or 'aucune'}")
            return texte + (f" ; indéterminées : {', '.join(indet)}." if indet else ".")
        if outil in ("simuler_ordre", "simuler_scenario"):
            v = r.get("verdict", {})
            texte = f"Scénario : {decrire_ordres(r.get('ordres') or [])}. " if outil == "simuler_scenario" else ""
            # Pas de note globale : l'angle le plus faible décide, avec la phrase du moteur s'il en donne une.
            dim, mes = r.get("dimension_min"), r.get("mesure_min")
            m = ((((r.get("apres") or {}).get("notes") or {}).get(dim) or {}).get("mesures") or {}).get(mes) or {}
            phrase = f" ({m['phrase']})" if isinstance(m.get("phrase"), str) else ""
            texte += (f"Verdict : {v.get('libelle')} ; angle déterminant : {libelle_famille(r, dim)} / "
                      f"{_mesure(mes)}{phrase} ; {r.get('direction', {}).get('libelle')}.")
            so = r.get("solidite") or {}
            if so.get("libelle"):
                texte += f" Solidité : {so['libelle'].lower()}."
            cs = r.get("contraintes_strictes", {})
            if cs.get("violee"):
                texte += f" Contrainte stricte violée : {', '.join(_etiquette(t) for t in cs.get('themes_violes') or [])}."
            op = r.get("operation") or {}
            if op.get("code") not in (None, "comptant"):
                texte += (f" {op.get('libelle')} : levier {_nombre(op.get('levier_apres'), 2)}, contrôle d'expérience "
                          f"« {(op.get('controle_experience') or {}).get('niveau')} ».")
            return texte
        if outil == "chercher_taille_compatible":
            if not r.get("lancee", True):
                return f"Recherche non lancée : {r.get('raison')}"
            if r.get("taille_compatible_pct") is None:
                return f"Aucune taille compatible jusqu'à {_nombre(r.get('taille_demandee_pct'))} %."
            return (f"Taille compatible : {_nombre(r.get('taille_compatible_pct'))} % sur "
                    f"{_nombre(r.get('taille_demandee_pct'))} % demandés ({ISSUES.get(r.get('issue'), r.get('issue'))}).")
        if outil == "lister_instruments":
            return f"{r.get('nombre')} instruments (classe : {CLASSES.get(r.get('classe'), r.get('classe'))})."
        if outil == "decrire_apport":
            ap = r.get("apres_ordre") or {}
            corr = (r.get("correlation_portefeuille") or {}).get("valeur")
            texte = f"Apport de {r.get('ticker')} au portefeuille"
            if corr is not None:
                texte += f" : corrélation {_nombre(corr, 2)} avec le portefeuille"
            if ap.get("part_du_risque_pct") is not None:
                texte += f", part du risque après l'ordre {_nombre(ap['part_du_risque_pct'])} %"
            return texte + f" ; {len(r.get('candidats') or [])} instruments proches de la même classe."
        if outil == "juger_pistes":
            if r.get("decision") == "suffisant":
                return "Pistes jugées suffisantes."
            pistes = r.get("pistes") or []
            return f"Recherche complémentaire faite : {len(pistes)} piste(s) retenue(s)."
        if outil == "envoyer_explorateur":
            pistes = r.get("pistes") or []
            liste = " ; ".join(f"{p.get('piste')} : {str(p.get('verdict') or '').lower()}" for p in pistes)
            if r.get("statut") == "repli":
                return f"{r.get('avis')} {liste}".strip()
            return f"Explorateur revenu avec {len(pistes)} piste(s) testée(s) : {liste}."
    except Exception:
        pass
    return "Résultat reçu."


def resume_etape(outil: str, arguments: dict, resultat, ticker_ordre: str | None = None) -> str:
    """Résumé d'une étape, tel que la trace et le suivi en direct l'affichent."""
    resume = resumer(outil, resultat)
    if outil == "simuler_ordre" and ticker_ordre:
        ticker = str((arguments or {}).get("ticker", "")).strip().upper()
        if ticker and ticker != str(ticker_ordre).strip().upper():
            resume = f"Substitut testé ({ticker}) : {resume}"
    return resume


def _taille(x) -> str:
    """Un pourcentage d'ordre sans décimale inutile : 15 → « 15 », 7.5 → « 7,5 »."""
    try:
        return f"{float(x):g}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def decrire_ordres(ordres: list) -> str:
    """« achat de 7,5 % de TSLA, achat de 7,5 % de XIU.TO »."""
    return ", ".join(f"{o.get('sens')} de {_taille(o.get('pourcentage'))} % de {o.get('ticker')}" for o in ordres or [])


def extraire_trace(messages, ticker_ordre: str | None = None) -> list:
    """Trace des appels d'outils, dans l'ordre, lue dans `agent.messages` (blocs toolUse et toolResult)."""
    appels, resultats = [], {}
    for message in messages or []:
        for bloc in message.get("content", []):
            if not isinstance(bloc, dict):
                continue
            if "toolUse" in bloc:
                appels.append(bloc["toolUse"])
            elif "toolResult" in bloc:
                resultats[bloc["toolResult"].get("toolUseId")] = bloc["toolResult"]
    trace = []
    ticker_ordre = str(ticker_ordre).strip().upper() if ticker_ordre else None
    for etape, appel in enumerate(appels, start=1):
        outil = appel.get("name")
        arguments = appel.get("input") or {}
        resultat = _contenu_resultat(resultats.get(appel.get("toolUseId")))
        if outil == "simuler_ordre" and ticker_ordre is None:
            ticker_ordre = str(arguments.get("ticker", "")).strip().upper()
        resume = resume_etape(outil, arguments, resultat, ticker_ordre)
        trace.append({"etape": etape, "outil": outil, "arguments": arguments,
                      "resultat_resume": resume, "resultat": resultat})
    return trace


def extraire_substitut(trace: list, ticker_ordre: str) -> dict | None:
    """Le substitut testé par l'agent : un `simuler_ordre` sur un autre symbole que celui de l'ordre."""
    ticker_ordre = str(ticker_ordre).strip().upper()
    for e in trace or []:
        if e.get("outil") != "simuler_ordre":
            continue
        ticker = str((e.get("arguments") or {}).get("ticker", "")).strip().upper()
        r = e.get("resultat")
        if ticker and ticker != ticker_ordre and isinstance(r, dict) and "erreur" not in r:
            return {"ticker": ticker, "etape": e.get("etape"), "verdict": r.get("verdict"), "score": r.get("score"),
                    "dimension_min": r.get("dimension_min"), "mesure_min": r.get("mesure_min"),
                    "direction": r.get("direction"), "solidite": (r.get("solidite") or {}).get("statut"),
                    "pourcentage": (r.get("ordre") or {}).get("pourcentage"),
                    "nature": "possibilite_testee",
                    "avertissement": "Possibilité testée par l'agent, pas une recommandation."}
    return None


# --- Pistes testées ------------------------------------------------------------------------------

FAMILLES = {"montant_reduit": "Montant plus petit", "autre_instrument": "Autre instrument",
            "achat_partage": "Achat partagé avec un fonds diversifié",
            "vente_pour_financer": "Achat payé par une vente", "combinaison": "Combinaison",
            "achat_reparti": "Achat réparti sur plusieurs titres", "autre_operation": "Autre opération"}


def _est_fonds(ticker) -> bool:
    try:
        from moteur import instruments
        return bool(instruments.est_fonds(str(ticker).strip().upper()))
    except Exception:
        return False


def _ordre(ticker, sens, pourcentage, operation=None) -> dict:
    o = {"ticker": str(ticker).strip().upper(), "sens": str(sens).strip().lower(), "pourcentage": float(pourcentage)}
    if operation and operation != "comptant":
        o["operation"] = operation
    return o


def _piste(famille, description, ordres, r, etape) -> dict:
    v = r.get("verdict") or {}
    d = r.get("direction") or {}
    angle = {"famille": r.get("dimension_min"), "mesure": r.get("mesure_min"),
             "libelle": f"{libelle_famille(r, r.get('dimension_min'))} ({_mesure(r.get('mesure_min'))})"
             if r.get("dimension_min") else None}
    return {"famille": famille, "libelle_famille": FAMILLES[famille], "description": description, "ordres": ordres,
            "raison": None, "angle_le_plus_faible": angle,
            "verdict": {"code": v.get("code"), "libelle": v.get("libelle")}, "score": r.get("score"),
            "direction": {"cas": d.get("cas"), "libelle": d.get("libelle")} if d else None, "etape": etape}


def _piste_simulation(r: dict, ordre_demande: dict, etape) -> dict | None:
    """Une simulation (simuler_ordre ou simuler_scenario) lue comme une piste, ou None si c'est l'ordre lui-même."""
    from moteur.notation import EPS

    jambes = r.get("ordres") or [r.get("ordre") or {}]
    t0, s0, p0 = ordre_demande["ticker"], ordre_demande["sens"], ordre_demande["pourcentage"]
    lisibles = [_ordre(j.get("ticker"), j.get("sens"), j.get("pourcentage"), j.get("operation")) for j in jambes]
    ventes = [j for j in lisibles if j["sens"] == "vente"]
    achats = [j for j in lisibles if j["sens"] == "achat"]
    if len(lisibles) == 1:
        j = lisibles[0]
        if j["ticker"] == t0 and j["sens"] == s0:
            if abs(j["pourcentage"] - p0) < EPS:
                return None
            return _piste("montant_reduit", f"{s0.capitalize()} de {_taille(j['pourcentage'])} % au lieu de "
                          f"{_taille(p0)} % ({t0})", lisibles, r, etape)
        if j["sens"] != s0:   # une vente proposée pour un achat demandé, ou l'inverse : une autre opération
            return _piste("autre_operation", f"{j['sens'].capitalize()} de {_taille(j['pourcentage'])} % de "
                          f"{j['ticker']} au lieu de : {s0} de {_taille(p0)} % de {t0}", lisibles, r, etape)
        return _piste("autre_instrument", f"{j['sens'].capitalize()} de {_taille(j['pourcentage'])} % de "
                      f"{j['ticker']} à la place de {t0}", lisibles, r, etape)
    if ventes and achats:
        a = ", ".join(f"{_taille(j['pourcentage'])} % de {j['ticker']}" for j in achats)
        v = ", ".join(f"{_taille(j['pourcentage'])} % de {j['ticker']}" for j in ventes)
        # Une vente qui paie un achat partagé ou réduit combine plusieurs familles.
        famille = "vente_pour_financer" if len(achats) == 1 and achats[0]["ticker"] == t0 else "combinaison"
        return _piste(famille, f"Achat de {a} payé en partie par la vente de {v}"
                      if sum(j["pourcentage"] for j in ventes) < sum(j["pourcentage"] for j in achats) - EPS
                      else f"Achat de {a} payé par la vente de {v}", lisibles, r, etape)
    if len(achats) >= 2 and t0 in [j["ticker"] for j in achats] and sum(j["pourcentage"] for j in achats) < p0 - EPS:
        return _piste("combinaison", "Montant plus petit avec un complément : " + ", ".join(
            f"{_taille(j['pourcentage'])} % de {j['ticker']}" for j in lisibles), lisibles, r, etape)
    autres = [j for j in achats if j["ticker"] != t0]
    famille = "achat_partage" if autres and all(_est_fonds(j["ticker"]) for j in autres) else "achat_reparti"
    return _piste(famille, ("Achat partagé : " if famille == "achat_partage" else "Achat réparti : ") + ", ".join(
        f"{_taille(j['pourcentage'])} % de {j['ticker']}" for j in lisibles), lisibles, r, etape)


def extraire_pistes(trace: list, ticker, sens, pourcentage, operation="comptant") -> list:
    """Les pistes testées, dans l'ordre, construites par le code à partir des résultats des outils de la trace.

    Chaque piste : `famille`, `libelle_famille`, `description`, `ordres`, `verdict` ({code, libelle}), `score`,
    `direction` ({cas, libelle}) et `etape`. Le texte du modèle n'y entre jamais ; un appel en erreur n'en fait pas.
    """
    from moteur import notation

    demande = _ordre(ticker, sens, pourcentage)
    pistes, score_avant = [], None
    for e in trace or []:
        r = e.get("resultat")
        if not isinstance(r, dict) or "erreur" in r:
            continue
        if e.get("outil") in ("simuler_ordre", "simuler_scenario"):
            if score_avant is None:
                score_avant = (r.get("avant") or {}).get("score")
            p = _piste_simulation(r, demande, e.get("etape"))
            if p:
                p["raison"] = (e.get("arguments") or {}).get("raison")
                pistes.append(p)
        elif e.get("outil") == "chercher_taille_compatible" and r.get("lancee", True) and r.get("courbe"):
            courbe = r["courbe"]
            taille = r.get("taille_compatible_pct")
            point = (next(p for p in courbe if p["taille_pct"] == taille) if taille is not None
                     else max(courbe, key=lambda p: p["score"]))
            v = notation.verdict(r.get("contraintes_strictes") or {"violee": False, "themes_violes": []}, point["score"])
            d = notation.direction(score_avant, point["score"]) if score_avant is not None else {}
            t = str(r.get("ticker") or demande["ticker"]).strip().upper()
            sens = str(r.get("sens") or demande["sens"]).strip().lower()
            meme = t == demande["ticker"] and sens == demande["sens"]
            if taille is not None and meme:
                description = (f"{sens.capitalize()} de {_taille(taille)} % au lieu de "
                               f"{_taille(r.get('taille_demandee_pct'))} % ({t})")
            elif taille is not None:   # la taille cherchée sur un autre instrument : c'est un autre instrument
                description = f"{sens.capitalize()} de {_taille(taille)} % de {t} à la place de {demande['ticker']}"
            else:
                description = f"Aucun montant compatible jusqu'à {_taille(r.get('taille_demandee_pct'))} % ({t})"
            famille = "montant_reduit" if meme else ("autre_instrument" if sens == demande["sens"] else "autre_operation")
            pistes.append(_piste(famille, description,
                                 [_ordre(t, sens, point["taille_pct"], r.get("operation"))],
                                 {"verdict": v, "score": point["score"], "direction": d,
                                  "dimension_min": point.get("dimension_min"), "mesure_min": point.get("mesure_min")},
                                 e.get("etape")))
            pistes[-1]["raison"] = (e.get("arguments") or {}).get("raison")
    return pistes


# --- Erreurs ------------------------------------------------------------------------------------

def message_erreur(e: Exception) -> str:
    """Message court en français ; jamais le texte brut de l'exception (il peut contenir un identifiant AWS)."""
    code = ""
    reponse = getattr(e, "response", None)
    if isinstance(reponse, dict):
        code = str(reponse.get("Error", {}).get("Code", ""))
    nom = type(e).__name__
    indice = f"{nom} {code} {e}"
    if "NoCredentials" in nom or "PartialCredentials" in nom:
        return "Identifiants AWS absents : Bedrock n'a pas pu être appelé."
    if "ExpiredToken" in indice or "UnrecognizedClient" in indice or "InvalidClientTokenId" in indice:
        return "Identifiants AWS expirés ou invalides : Bedrock n'a pas répondu."
    if "AccessDenied" in indice:
        return "Accès refusé par Bedrock pour ce modèle."
    if "Throttl" in indice:
        return "Bedrock limite le débit des appels : réessayez dans un instant."
    if "EndpointConnection" in nom or "ConnectTimeout" in nom or "ReadTimeout" in nom:
        return "Bedrock est injoignable (réseau ou délai dépassé)."
    return f"Bedrock n'a pas répondu ({nom})."


# --- Point d'entrée -----------------------------------------------------------------------------

# Mémoire des analyses : une analyse identique en cours est partagée, une analyse finie est rejouée.
# GLC_MEMOIRE=0 revient au comportement d'avant (chaque appel refait l'analyse).
MEMOIRE = os.environ.get("GLC_MEMOIRE", "1").strip() != "0"


def cle_analyse(client, ticker, sens, pourcentage, operation, modele, equipe, chef) -> str | None:
    """Ce qui rend deux demandes identiques : le contenu de la fiche tel que le moteur la lit, l'ordre, les réglages,
    les consignes des agents et la version du garde-fou. None si la fiche est illisible."""
    import hashlib

    fiche = _api_moteur.lire_fiche_client(client)
    if not isinstance(fiche, dict) or "erreur" in fiche:
        return None
    consignes = "".join(f.read_text(encoding="utf-8") for f in sorted(PROMPT_SYSTEME.parent.glob("*.md")))
    config = _garde_fou.configuration_garde_fou() or {}
    try:
        montant = round(float(pourcentage), 4)
    except (TypeError, ValueError):
        montant = str(pourcentage)
    # Empreinte de la réponse du moteur pour cette fiche et cet ordre (verdict, notes, mesures, solidité, montant
    # compatible) : un changement de code ou de données qui change un chiffre change la clé. Sans réponse, pas de clé.
    simulation = _api_moteur.simuler_ordre(client, ticker, sens, pourcentage, operation or "comptant")
    taille = _api_moteur.chercher_taille_compatible(client, ticker, sens, pourcentage, operation or "comptant")
    if not isinstance(simulation, dict) or "erreur" in simulation or not isinstance(taille, dict) or "erreur" in taille:
        return None
    moteur = {"simulation": {k: v for k, v in simulation.items() if k != "sources"},
              "taille": {k: v for k, v in taille.items() if k != "sources"}}
    contenu = {"client": {k: v for k, v in fiche.items() if k != "sources"},
               "moteur": hashlib.sha256(json.dumps(moteur, sort_keys=True, ensure_ascii=False,
                                                   default=str).encode()).hexdigest(),
               "ordre": [str(ticker).strip().upper(), str(sens).strip().lower(), montant,
                         str(operation or "comptant").strip().lower()],
               "reglages": [nom_modele(modele), equipe, chef, EFFORT, EFFORT_EXPLORATEUR, config.get("version")],
               "consignes": hashlib.sha256(consignes.encode("utf-8")).hexdigest()}
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant", sur_etape=None,
              equipe=None, modele_explorateur=None, chef=None, relancer: bool = False, memoire=None,
              tracer=None) -> dict:
    """Fait analyser l'ordre par les agents. Ne lève jamais d'exception.

    Deux demandes identiques partagent l'analyse en cours ; une analyse finie et réussie est rejouée avec ses étapes
    (`memoire.statut` = « deja_faite », « partagee » ou « nouvelle » ; None sans mémoire). `relancer=True` refait
    l'analyse. La mémoire s'applique au vrai Bedrock (`memoire=None`), ou partout avec `memoire=True`.
    Les autres arguments : voir `analyser`.
    """
    reel = modele is None or isinstance(modele, str)
    utiliser = MEMOIRE and (memoire if memoire is not None else reel)
    tracer = reel if tracer is None else bool(tracer)

    def faire(diffuser):
        """L'analyse, puis sa trace (identifiant dans le résultat, écriture en fond) : jamais d'effet sur l'analyse."""
        r = analyser(client, ticker, sens, pourcentage, modele, operation, diffuser, equipe, modele_explorateur, chef)
        r["trace_aws"] = None
        if tracer:
            try:
                from . import traces as _traces
                fiche = _api_moteur.lire_fiche_client(client)
                ordre = {"ticker": str(ticker).strip().upper(), "sens": str(sens).strip().lower(),
                         "pourcentage": pourcentage, "operation": str(operation or "comptant").strip().lower()}
                reglages = {"modeles": {"principal": r.get("modele"),
                                        "explorateur": nom_modele(modele_explorateur if modele_explorateur is not None
                                                                  else modele)},
                            "equipe": EQUIPE if equipe is None else bool(equipe),
                            "chef": CHEF if chef is None else bool(chef), "effort": EFFORT,
                            "effort_explorateur": EFFORT_EXPLORATEUR, "memoire": MEMOIRE}
                identifiant = _traces.preparer(r, fiche if isinstance(fiche, dict) else {}, ordre, reglages)
                r["trace_aws"] = {"id": identifiant} if identifiant else None
            except Exception:
                r["trace_aws"] = None
        return r

    cle = None
    if utiliser:
        try:
            cle = cle_analyse(client, ticker, sens, pourcentage, operation, modele,
                              EQUIPE if equipe is None else bool(equipe), chef if chef is not None else CHEF)
        except Exception:
            cle = None
    if cle is None:
        r = faire(sur_etape)
        r["memoire"] = None
        return r
    from . import memoire as _memoire
    return _memoire.partager(cle, faire, sur_etape=sur_etape, relancer=relancer)


def analyser(client, ticker, sens, pourcentage, modele=None, operation="comptant", sur_etape=None,
             equipe=None, modele_explorateur=None, chef=None) -> dict:
    """Fait analyser l'ordre par les agents. Ne lève jamais d'exception.

    `equipe` (par défaut le réglage `EQUIPE`) : le chef de dossier, qui envoie l'explorateur pour un ordre en
    tension ; False : l'agent seul d'avant. `modele_explorateur` : le modèle de l'explorateur (par défaut le même).

    `sur_etape(evenement)`, si elle est donnée, reçoit chaque étape au moment où un agent la fait (voir
    `agent/suivi.py` pour la forme des événements). `debut_outil`, `fin_outil` et `redaction` arrivent des fils
    où Strands fait tourner les agents ; `verification`, `correction` et `fin`, du fil qui appelle `inspecter`.
    Une fonction qui lève une exception ne casse pas l'analyse.
    """
    debut = time.monotonic()
    equipe = EQUIPE if equipe is None else bool(equipe)
    chef = equipe and (CHEF if chef is None else bool(chef))
    T, S = str(ticker).strip().upper(), str(sens).strip().lower()
    op = str(operation or "comptant").strip().lower()
    compteur = Compteur()
    suivi = Suivi(sur_etape, agent="principal", ticker_ordre=T, compteur=compteur)
    agent, explication, erreur, trace = None, None, None, []
    envoi = {"resultat": None, "mission": None, "refus": [], "explorateur": None, "mode": None, "jugements": []}
    config = _garde_fou.configuration_garde_fou()
    simule = not (modele is None or isinstance(modele, str))
    etat_garde_fou = {"actif": bool(config) and not simule, "version": config["version"] if config else None,
                      "intervenu": False}
    try:
        modele_nom = nom_modele(modele)
    except Exception:
        modele_nom = str(modele)

    def envoyer(mission: str) -> dict:
        """Règles du code pour l'envoi : un ordre en tension seulement, une seule fois."""
        if envoi["resultat"] is not None:
            return {"erreur": "L'explorateur a déjà été envoyé pour cette analyse."}
        sim = _api_moteur.simuler_ordre(client, T, S, pourcentage, op)
        if "erreur" in sim:
            return {"erreur": sim["erreur"]}
        code = sim["verdict"]["code"]
        permis = ("en_tension", "incompatible") if chef else ("en_tension",)
        if code not in permis:
            refus = ("L'explorateur n'est envoyé que pour un ordre « en tension » : "
                     + ("une contrainte stricte est violée, et rien ne la répare." if code == "incompatible"
                        else "l'ordre est déjà compatible.")) if not chef else \
                "L'explorateur n'est pas envoyé pour un ordre déjà compatible."
            envoi["refus"].append(refus)
            return {"erreur": refus}
        envoi["mission"] = mission
        envoi["mode"] = "remplacer" if code == "incompatible" else "ajuster"
        if isinstance(mission, dict) and code == "incompatible":
            mission = {**mission, "mandat": "remplacer l'instrument : aucun montant ne répare une règle stricte"}
        envoi["explorateur"] = _explorateur.Explorateur(
            client, {"ticker": T, "sens": S, "pourcentage": float(pourcentage), "operation": op}, sim,
            modele=modele_explorateur if modele_explorateur is not None else modele, sur_etape=sur_etape,
            compteur=compteur, mode=envoi["mode"], sous_mandat=isinstance(mission, dict))
        envoi["resultat"] = envoi["explorateur"].lancer(mission)
        return envoi["resultat"]["retour"]

    def juger(decision: str, critique: str) -> dict:
        """Règles du code pour le jugement : après un retour de l'explorateur, un seul renvoi."""
        if envoi["explorateur"] is None:
            return {"erreur": "Aucun travail de l'explorateur à juger."}
        if decision not in ("suffisant", "a_completer"):
            return {"erreur": "decision vaut « suffisant » ou « a_completer »."}
        envoi["jugements"].append({"decision": decision, "critique": critique or None})
        if decision == "suffisant":
            return {"decision": "suffisant", "message": "Pistes jugées suffisantes : rédige le rapport."}
        # Le second tour tient dans le budget de l'analyse : sinon, le chef de dossier rédige avec ce qu'il a.
        reste = BUDGET_ANALYSE_S - (time.monotonic() - debut) - TEMPS_REDACTION_S
        if reste < MINIMUM_SECOND_TOUR_S:
            envoi["jugements"][-1]["refuse"] = True
            return {"erreur": "Plus assez de temps pour une recherche complémentaire : rédige le rapport avec ces pistes."}
        r = envoi["explorateur"].reprendre(critique, delai_s=reste)
        if "erreur" in r:
            envoi["jugements"][-1]["refuse"] = True
            return r
        envoi["resultat"] = r
        return {"decision": "a_completer", **r["retour"]}

    try:
        agent = creer_agent(client, modele, suivi=suivi, envoyer=envoyer if equipe else None,
                            juger=juger if chef else None)
        resultat = agent(consigne(identifiant_client(client), T, S, pourcentage, op),
                         limits={"turns": (LIMITE_TOURS_PRINCIPAL + (2 if chef else 0)) if equipe else LIMITE_TOURS})
        explication = texte_final(getattr(resultat, "message", None))
        if getattr(resultat, "stop_reason", "") == "guardrail_intervened":
            etat_garde_fou["intervenu"] = True
            explication = None
            erreur = "Le garde-fou Bedrock a retenu l'explication : le rapport est affiché sans elle."
        elif explication is None:
            erreur = ("L'agent n'a pas rédigé d'explication dans la limite de tours."
                      if getattr(resultat, "stop_reason", "") == "limit_turns"
                      else "L'agent n'a pas rédigé d'explication.")
    except Exception as e:
        erreur = message_erreur(e)
    explo = envoi["resultat"]
    try:
        trace = fusionner_traces(extraire_trace(agent.messages, T) if agent is not None else [],
                                 (explo or {}).get("trace") or [])
    except Exception:
        trace = []
    requete = consigne(identifiant_client(client), T, S, pourcentage)
    ancrage = _verifier(explication, trace, requete, simule, suivi)
    correction = {"faite": False, "motifs": []}
    sim = next((e.get("resultat") for e in trace if e.get("outil") == "simuler_ordre" and e.get("agent") == "principal"
                and isinstance(e.get("resultat"), dict)), None) or {}
    direction = None if (sim.get("contraintes_strictes") or {}).get("violee") else sim.get("direction")
    motifs = motifs_de_correction(ancrage, explication, direction) if explication else []
    if motifs and agent is not None and not etat_garde_fou["intervenu"]:
        # Une seule réécriture, vérifiée à son tour ; si elle échoue aussi, l'avis de la vérification reste.
        suivi.emettre("correction")
        correction = {"faite": True, "motifs": motifs, "reussie": False}
        try:
            reponse = agent(consigne_correction(motifs), limits={"turns": 2})
            nouveau = texte_final(getattr(reponse, "message", None))
            if getattr(reponse, "stop_reason", "") != "guardrail_intervened" and nouveau:
                explication = nouveau
                trace = fusionner_traces(extraire_trace(agent.messages, T), (explo or {}).get("trace") or [])
                ancrage = _verifier(explication, trace, requete, simule, suivi)
                correction["reussie"] = not motifs_de_correction(ancrage, explication, direction)
        except Exception:
            pass
        trace = trace + [{"etape": len(trace) + 1, "agent": "principal", "outil": "corriger_le_texte",
                          "arguments": {}, "resultat": {"motifs": motifs, "reussie": correction["reussie"]},
                          "resultat_resume": ("L'agent a corrigé son texte après vérification."
                                              if correction["reussie"] else
                                              "L'agent a réécrit son texte après vérification ; des problèmes restent.")}]
    if not etat_garde_fou["actif"]:
        etat_garde_fou["avis"] = ("Garde-fou Bedrock non configuré : les appels au modèle ne sont pas filtrés."
                                  if config is None else "Modèle simulé : garde-fou non appliqué.")
    if explo is not None:
        pistes = pistes_dans_la_trace(explo.get("pistes") or [], trace)
    else:
        pistes = _pistes_sures(trace, T, S, pourcentage)
    suivi.emettre("fin")
    return {"explication": explication, "trace": trace, "modele": modele_nom,
            "duree_s": round(time.monotonic() - debut, 2), "erreur": erreur,
            "garde_fou": etat_garde_fou, "ancrage": ancrage,
            "substitut": extraire_substitut(trace, T), "pistes": pistes,
            # La finalité supposée est l'hypothèse du chef de dossier (son mandat) ; sans chef, celle de l'explorateur.
            "intention": ((envoi["mission"] or {}).get("finalite_supposee") if isinstance(envoi["mission"], dict)
                          else (explo or {}).get("intention")),
            "agents": decrire_agents(equipe, trace, envoi), "correction": correction}


def _verifier(explication, trace, requete, simule, suivi) -> dict:
    if explication:
        suivi.emettre("verification")
    try:
        return _garde_fou.verifier_ancrage(explication, trace, requete, utiliser_garde_fou=not simule)
    except Exception:
        return {"statut": "indisponible", "message": "Vérification de l'ancrage impossible."}


LIMITE_MOTS = 180


def nombre_de_mots(texte: str | None) -> int:
    """Le plus strict de deux comptes (mots du texte, morceaux séparés par des espaces) : la limite tient pour les deux."""
    return max(len(re.findall(r"[\w’'-]*\w", texte or "")), len((texte or "").split()))


CONTRAIRES_DIRECTION = {
    "reste_dans_la_politique": r"fait sortir|faire sortir|sort de la politique|hors politique",
    "fait_sortir_de_la_politique": r"aggrave|rapproche|déjà hors|reste dans la politique",
    "hors_politique_rapproche": r"fait sortir|faire sortir|aggrave|reste dans la politique",
    "hors_politique_aggrave": r"fait sortir|faire sortir|vous fait sortir|rapproche|reste dans la politique",
}


def motifs_de_correction(ancrage: dict, explication: str | None = None, direction: dict | None = None) -> list:
    """Les problèmes trouvés par les contrôles (chiffres non sourcés, passage non appuyé, longueur), en français."""
    motifs = []
    if (ancrage or {}).get("statut") == "non_appuyee":
        motifs = [f"Le chiffre {c} ne figure dans aucun résultat d'outil."
                  for c in ancrage.get("chiffres_non_sources") or []]
        if not motifs:
            motifs.append("Le garde-fou Bedrock ne trouve pas l'appui d'un passage dans les résultats des outils : "
                          + str(ancrage.get("message", "")))
    if explication and re.search(r"exclu[a-z]*[^.]*(débutant|expérience)|(débutant|expérience)[^.]*exclu", explication,
                                 flags=re.IGNORECASE):
        motifs.append("Le texte dit qu'une opération est exclue à cause de l'expérience : c'est faux, l'expérience ne "
                      "change pas le verdict, seules les pistes de l'explorateur restent au comptant.")
    interdits = sorted({m.group(0).lower() for m in re.finditer(r"\b(scores?|maillons?|cha[iî]nes?|dimensions?)\b",
                                                                 explication or "", flags=re.IGNORECASE)})
    if interdits:
        motifs.append("Le texte emploie " + ", ".join(f"« {m} »" for m in interdits) + " : dis « angle », « note », "
                      "et « l'angle déterminant » pour celui dont la note est la plus basse.")
    if explication and re.search(r"\b(19|20)\d{2}\b", explication):
        motifs.append("Le texte cite une année ou une date : n'en écris aucune ; dis « dans sa pire année », « sur "
                      "cinq ans de données ».")
    cas = (direction or {}).get("cas")
    if explication and cas in CONTRAIRES_DIRECTION and re.search(CONTRAIRES_DIRECTION[cas], explication,
                                                                   flags=re.IGNORECASE):
        motifs.append(f"La direction écrite contredit celle du moteur, « {(direction or {}).get('libelle')} » : "
                      "reprends-la telle quelle.")
    mots = nombre_de_mots(explication)
    if mots > LIMITE_MOTS:
        motifs.append(f"Le texte compte {mots} mots ; la limite absolue est de {LIMITE_MOTS} mots.")
    return motifs


def consigne_correction(motifs: list) -> str:
    return ("Vérification de ton rapport par le code et le garde-fou : des problèmes ont été trouvés.\n- "
            + "\n- ".join(motifs) +
            "\nRéécris le rapport complet une fois, dans la même structure, en 120 mots au plus, sans appeler d'outil. "
            "N'écris que des chiffres présents dans les résultats des outils ; retire ou remplace les autres.")


def fusionner_traces(trace_principal: list, trace_explorateur: list) -> list:
    """Les étapes de l'explorateur se placent à leur moment : son premier tour juste après `envoyer_explorateur`, son
    second tour juste après le `juger_pistes` qui l'a demandé. Chaque étape porte `agent` ; une étape de l'explorateur
    garde son numéro à lui dans `etape_explorateur`."""
    par_tour: dict = {}
    for x in trace_explorateur:
        par_tour.setdefault(x.get("tour", 1), []).append({**x, "agent": "explorateur",
                                                           "etape_explorateur": x.get("etape")})
    fusion = []
    for e in trace_principal:
        fusion.append({**e, "agent": "principal"})
        if e.get("outil") == "envoyer_explorateur" and 1 in par_tour:
            fusion += par_tour.pop(1)
        elif (e.get("outil") == "juger_pistes" and 2 in par_tour
              and str((e.get("arguments") or {}).get("decision", "")).lower() == "a_completer"):
            fusion += par_tour.pop(2)
    for reste in par_tour.values():
        fusion += reste
    for i, e in enumerate(fusion, start=1):
        e["etape"] = i
    return fusion


def pistes_dans_la_trace(pistes: list, trace: list) -> list:
    """Les pistes de l'explorateur, avec le numéro de leur étape dans la trace fusionnée."""
    numeros = {e.get("etape_explorateur"): e["etape"] for e in trace if e.get("agent") == "explorateur"}
    return [dict(p, etape=numeros.get(p.get("etape"))) for p in pistes]


ROLES = {"principal": "Chef de dossier : monte le dossier de A à Z et rédige l'explication.",
         "explorateur": "Chercheur de pistes : envoyé pour un ordre en tension, il cherche et teste des pistes."}


def decrire_agents(equipe: bool, trace: list, envoi: dict) -> list:
    """Qui a fait quoi, pour le rapport."""
    def etapes(nom):
        return [e["etape"] for e in trace if e.get("agent") == nom]
    agents = [{"nom": "principal", "role": ROLES["principal"] if equipe else "Agent seul : monte le dossier et "
               "rédige l'explication.", "etapes": etapes("principal")}]
    if not equipe:
        return agents
    explo = envoi.get("resultat")
    if explo is None:
        statut, avis = "non_envoye", (envoi["refus"][-1] if envoi.get("refus") else
                                      "Non envoyé : l'ordre n'est pas en tension.")
    else:
        statut, avis = explo.get("statut"), explo.get("avis")
    if envoi.get("jugements") is not None:
        agents[0]["jugements"] = envoi["jugements"]
        agents[0]["mandat"] = envoi.get("mode")
    agents.append({"nom": "explorateur", "role": ROLES["explorateur"], "statut": statut, "avis": avis,
                   "mission": envoi.get("mission"), "etapes": etapes("explorateur"),
                   "bilan": (explo or {}).get("bilan"), "cause_lue": (explo or {}).get("cause_lue"),
                   "raison_du_repli": (explo or {}).get("raison_du_repli")})
    return agents


def _pistes_sures(trace, ticker, sens, pourcentage) -> list:
    try:
        return extraire_pistes(trace, ticker, sens, pourcentage)
    except Exception:
        return []


def _afficher(r: dict) -> None:
    print("=== Explication ===")
    print(r["explication"] or "(aucune)")
    print("\n=== Trace ===")
    for e in r["trace"]:
        print(f"{e['etape']}. {e['outil']}({json.dumps(e['arguments'], ensure_ascii=False)})")
        print(f"   → {e['resultat_resume']}")
    print(f"\nAncrage : {r['ancrage'].get('message')}")
    print(f"Modèle : {r['modele']} · durée : {r['duree_s']} s")
    if r["erreur"]:
        print(f"Erreur : {r['erreur']}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) not in (4, 5):
        print("Usage : python -m agent.inspection <client> <ticker> <achat|vente> <pourcentage> [comptant|marge|decouvert]")
        return 2
    client, ticker, sens, pourcentage = argv[:4]
    operation = argv[4] if len(argv) == 5 else "comptant"
    try:
        pourcentage = float(pourcentage.replace(",", "."))
    except ValueError:
        print(f"Pourcentage invalide : « {pourcentage} ».")
        return 2
    r = inspecter(client, ticker, sens, pourcentage, operation=operation)
    _afficher(r)
    return 1 if r["erreur"] else 0


if __name__ == "__main__":
    sys.exit(main())
