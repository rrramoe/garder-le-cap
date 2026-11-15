"""Point d'entrée de l'agent d'inspection (Strands Agents sur Amazon Bedrock).

    inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant") -> dict

renvoie toujours `explication`, `trace`, `modele`, `duree_s`, `erreur`, `garde_fou` (état du garde-fou
Bedrock pendant l'inspection), `ancrage` (vérification de l'explication par les résultats des outils) et
`substitut` (l'instrument testé par l'agent à la place de celui de l'ordre, ou None),
sans jamais lever d'exception. Démo sans interface : `python -m agent.inspection robert TSLA achat 15`.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from . import garde_fou as _garde_fou
from . import identifiants
from .outils import creer_outils, identifiant_client

MODELE_DEFAUT = "global.anthropic.claude-sonnet-5"
REGION = identifiants.REGION
JETONS_SORTIE = 4000          # le bloc de raisonnement compte dans les jetons de sortie
LIMITE_TOURS = 10            # 7 tours dans le chemin le plus long (substitut compris), avec une marge
TENTATIVES_SDK = {"max_attempts": 4, "mode": "adaptive"}   # mode de tentatives de botocore (ThrottlingException)
PROMPT_SYSTEME = Path(__file__).parent / "prompts" / "systeme.md"


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


def creer_modele(model_id: str):
    from botocore.config import Config
    from strands.models import BedrockModel

    return BedrockModel(model_id=model_id, region_name=REGION, max_tokens=JETONS_SORTIE,
                        boto_client_config=Config(retries=TENTATIVES_SDK, read_timeout=120, connect_timeout=10),
                        **options_garde_fou())


def creer_agent(client, modele=None):
    """Agent Strands d'une inspection. `modele` : identifiant Bedrock, ou objet modèle Strands (essais)."""
    from strands import Agent, ModelRetryStrategy

    if modele is None or isinstance(modele, str):
        identifiants.charger_identifiants()
        modele = creer_modele(nom_modele(modele))
    return Agent(model=modele, tools=creer_outils(client), system_prompt=PROMPT_SYSTEME.read_text(encoding="utf-8"),
                 callback_handler=None, name="inspection",
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
              "ecarte_esg": "écarté ESG"}
NIVEAUX = {"essentiel": "essentiel", "standard": "standard", "detaille": "détaillé"}
DIMENSIONS = {"risque": "risque", "diversification": "diversification", "preferences": "préférences"}
MESURES = {"ampleur": "ampleur de la pire baisse", "duree": "durée sous l'eau", "classe_liquidites": "poids des liquidités",
           "classe_revenu_fixe": "poids du revenu fixe", "classe_actions": "poids des actions",
           "classe_alternatifs": "poids des titres alternatifs", "crypto": "poids des cryptoactifs",
           "plus_grosse_action": "plus grosse action", "plus_gros_fonds": "plus gros fonds",
           "plus_gros_secteur": "plus gros secteur"}
ISSUES = {"compatible_tel_quel": "compatible tel quel", "compatible_avec_ajustement": "compatible avec ajustement",
          "aucune_taille": "aucune taille"}
CLASSES = {"liquidites": "liquidités", "revenu_fixe": "revenu fixe", "actions": "actions",
           "alternatifs": "titres alternatifs", "toutes": "toutes"}


def _mesure(m) -> str:
    if isinstance(m, str) and m.startswith("theme_"):
        return f"thème « {ETIQUETTES.get(m[len('theme_'):], m[len('theme_'):])} »"
    return MESURES.get(m, ETIQUETTES.get(m, str(m).replace("_", " ")))


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
            noms = ", ".join(ETIQUETTES.get(n, n) for n in (c.get("theme", str(c)) if isinstance(c, dict) else str(c)
                                                            for c in contraintes))
            return (f"{r.get('nom')} : profil {d.get('profil', {}).get('libelle') or d.get('profil', {}).get('valeur')}, "
                    f"horizon {d.get('horizon_annees', {}).get('valeur')} ans, "
                    f"contraintes strictes : {noms or 'aucune'}, "
                    f"détail {NIVEAUX.get(d.get('niveau_detail', {}).get('valeur'), d.get('niveau_detail', {}).get('valeur'))}.")
        if outil == "lire_fiche_instrument":
            s = r.get("statistiques_cad", {})
            et = r.get("etiquettes", {})
            vraies = [ETIQUETTES.get(k, k) for k, v in et.items() if v.get("valeur") is True]
            indet = [ETIQUETTES.get(k, k) for k, v in et.items() if v.get("valeur") == "indetermine"]
            texte = (f"{r.get('nom')} ({CLASSES.get(r.get('classe_politique'), r.get('classe_politique'))}, "
                     f"{r.get('devise')}) : volatilité "
                     f"{_pct(s.get('volatilite_annualisee'))}, pire baisse {_pct(s.get('pire_baisse'))} ; "
                     f"étiquettes : {', '.join(vraies) or 'aucune'}")
            return texte + (f" ; indéterminées : {', '.join(indet)}." if indet else ".")
        if outil == "simuler_ordre":
            v = r.get("verdict", {})
            texte = (f"Verdict : {v.get('libelle')} ; score {_nombre(r.get('score'))} "
                     f"(avant {_nombre(r.get('avant', {}).get('score'))}) ; note la plus basse : "
                     f"{DIMENSIONS.get(r.get('dimension_min'), r.get('dimension_min'))} / {_mesure(r.get('mesure_min'))} ; "
                     f"{r.get('direction', {}).get('libelle')}.")
            so = r.get("solidite") or {}
            if so.get("libelle"):
                texte += f" Solidité : {so['libelle'].lower()}."
            cs = r.get("contraintes_strictes", {})
            if cs.get("violee"):
                texte += f" Contrainte stricte violée : {', '.join(ETIQUETTES.get(t, t) for t in cs.get('themes_violes') or [])}."
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
    except Exception:
        pass
    return "Résultat reçu."


def extraire_trace(messages) -> list:
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
    trace, ticker_ordre = [], None
    for etape, appel in enumerate(appels, start=1):
        outil = appel.get("name")
        arguments = appel.get("input") or {}
        resultat = _contenu_resultat(resultats.get(appel.get("toolUseId")))
        resume = resumer(outil, resultat)
        if outil == "simuler_ordre":
            ticker = str(arguments.get("ticker", "")).strip().upper()
            if ticker_ordre is None:
                ticker_ordre = ticker
            elif ticker != ticker_ordre:
                resume = f"Substitut testé ({ticker}) : {resume}"
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

def inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant") -> dict:
    """Fait inspecter l'ordre par l'agent. Ne lève jamais d'exception."""
    debut = time.monotonic()
    agent, explication, erreur, trace = None, None, None, []
    config = _garde_fou.configuration_garde_fou()
    simule = not (modele is None or isinstance(modele, str))
    etat_garde_fou = {"actif": bool(config) and not simule, "version": config["version"] if config else None,
                      "intervenu": False}
    try:
        modele_nom = nom_modele(modele)
    except Exception:
        modele_nom = str(modele)
    try:
        agent = creer_agent(client, modele)
        resultat = agent(consigne(identifiant_client(client), str(ticker).strip().upper(),
                                  str(sens).strip().lower(), pourcentage, str(operation or "comptant").strip().lower()),
                         limits={"turns": LIMITE_TOURS})
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
    try:
        trace = extraire_trace(agent.messages) if agent is not None else []
    except Exception:
        trace = []
    try:
        ancrage = _garde_fou.verifier_ancrage(explication, trace, consigne(
            identifiant_client(client), str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage),
            utiliser_garde_fou=not simule)
    except Exception:
        ancrage = {"statut": "indisponible", "message": "Vérification de l'ancrage impossible."}
    if not etat_garde_fou["actif"]:
        etat_garde_fou["avis"] = ("Garde-fou Bedrock non configuré : les appels au modèle ne sont pas filtrés."
                                  if config is None else "Modèle simulé : garde-fou non appliqué.")
    return {"explication": explication, "trace": trace, "modele": modele_nom,
            "duree_s": round(time.monotonic() - debut, 2), "erreur": erreur,
            "garde_fou": etat_garde_fou, "ancrage": ancrage,
            "substitut": extraire_substitut(trace, ticker)}


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
