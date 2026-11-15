"""Garder le cap : interface locale (Streamlit), prototype de service de gestion des risques.

Lancement : streamlit run app.py --server.address localhost

Le code calcule, le modèle explique : tous les chiffres affichés viennent de
moteur.api. L'agent (agent/inspection.py), s'il est présent, n'ajoute que
l'explication et la trace de ses appels.
"""

from __future__ import annotations

import copy
import inspect
import queue
import re
import threading
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from moteur import api, references

RACINE = Path(__file__).resolve().parent
BANDEAU = ("Simulation à but éducatif. Aucune transaction réelle. "
           "Ceci n'est pas un conseil financier personnalisé.")
AVIS_SANS_AGENT = ("Explication de l'agent indisponible : le rapport ci-dessous vient "
                   "directement du moteur de calcul")
LIMITE = 50

# Vocabulaire de l'action principale, en un seul endroit.
BOUTON_ACTION = "Analyser l'ordre"
TITRE_RAPPORT = "Analyse de l'ordre"
TITRE_ETAPES = "Étapes de l'analyse"
DEPUIS_PRECEDENT = "Depuis l'analyse précédente"
ATTENTE_AGENT = "L'agent rédige l'explication…"
EN_DIRECT_AGENT = "L'agent analyse votre ordre…"
DELAI_MAX_AGENT_S = 240  # au-delà, le rapport du moteur reste seul affiché

# Noms des agents de l'équipe, tels que montrés à l'écran.
NOMS_AGENTS = {"principal": "Agent principal", "explorateur": "Agent explorateur"}

# Analyse en direct : phrases montrées pendant le travail de l'agent (si l'agent n'en fournit pas).
LIBELLES_OUTILS = {
    "lire_fiche_client": "Je lis votre fiche.",
    "lire_fiche_instrument": "Je lis la fiche du titre.",
    "simuler_ordre": "Je simule l'ordre.",
    "chercher_taille_compatible": "Je cherche le montant compatible.",
}
LIBELLES_PHASES = {
    "redaction": "Je rédige l'explication.",
    "verification": "Je vérifie mon texte.",
    "correction": "Je corrige mon texte.",
}

# Ce que l'outil est : il renseigne, il ne conseille pas.
SOUS_TITRE = "Le service de gestion des risques de l'investisseur particulier (prototype)"
MISSION = ("L'outil renseigne, il ne conseille pas. Il vous aide à garder le cap sur vos objectifs : "
           "un placement est un moyen, pas une fin.")

# Palette : thème de la présentation du Datathon (marine, rouge, gris chauds, or, vert sauge).
MARINE = "#152532"
ROUGE_THEME = "#DE161D"
GRIS_CHAUD = "#F4F1EE"
GRIS_TEXTE = "#5F6368"
# Une couleur par verdict, distincte du marine des boutons.
COULEURS_VERDICT = {"compatible": "#1E7B4A", "en_tension": "#A35F00", "incompatible": "#B3121A"}
FONDS_VERDICT = {"compatible": "#E6F2EB", "en_tension": "#FDF1DC", "incompatible": "#FBE6E7"}
COULEURS_CLASSES = {"Actions": MARINE, "Revenu fixe": "#5B7A99", "Liquidités": "#A8C1B8",
                    "Titres alternatifs": "#F6C45E"}
COULEURS_POSITIONS = [MARINE, "#3C5A75", "#5B7A99", "#8BA6BF", "#A8C1B8", "#CFE0D8", "#F6C45E",
                      "#E8A33D", "#B9A99A", "#D9D5D0", "#6E6E71", "#9A8C7E"]

# Clients enregistrés : les trois exemples de l'énoncé ont la même forme qu'un nouveau client
# (fiche, portefeuille, valeur fictive en dollars canadiens, une ligne de description).
EXEMPLES_ENREGISTRES = [
    {"id": "robert", "valeur": 800_000,
     "description": "59 ans, proche de la retraite : épargne accumulée sur une carrière."},
    {"id": "mateo", "valeur": 250_000, "description": "41 ans, deux enfants : épargne en milieu de carrière."},
    {"id": "amira", "valeur": 50_000, "description": "26 ans, début de carrière : petite épargne qui grandit."},
]
NOUVEAU = "nouveau"
VALEUR_NOUVEAU = 100_000
# Réponses de départ d'un nouveau client : des valeurs neutres, signalées comme réponses par défaut.
REPONSES_PAR_DEFAUT = {"objectif": "croissance_equilibree", "horizon": "5_8", "fluctuations": "moderees",
                       "capacite_perte": "moderees", "besoin_liquidite": "aucun", "experience": "debutante"}

# Opérations et types d'ordre. Ajouter une opération (vente à découvert, achat sur marge)
# revient à ajouter une entrée ici : le formulaire n'a pas à changer.
OPERATIONS = {
    "achat": {"libelle": "Acheter", "nom": "Achat", "sens": "achat"},
    "vente": {"libelle": "Vendre", "nom": "Vente", "sens": "vente"},
    "marge": {"libelle": "Acheter sur marge", "nom": "Achat sur marge", "sens": "achat", "operation": "marge",
              "aide": "Opération avancée : l'achat peut dépasser vos liquidités. La différence est empruntée."},
    "decouvert": {"libelle": "Vendre à découvert", "nom": "Vente à découvert", "sens": "vente",
                  "operation": "decouvert",
                  "aide": "Opération avancée : vous vendez un titre emprunté, que vous ne détenez pas."},
}
# Mesure de préférence ajoutée par le moteur pour une opération avancée (expérience « intermédiaire »).
MESURES_OPERATION = {"achat_sur_marge": "argent emprunté", "vente_a_decouvert": "titres vendus à découvert"}


def operation_moteur(cle: str | None) -> str:
    """Opération du moteur (comptant, marge, decouvert) pour une opération du formulaire."""
    return OPERATIONS.get(cle or "", {}).get("operation", "comptant")
TYPES_ORDRE = {
    "marche": {"libelle": "Au marché", "prix": None,
               "aide": "Exécuté tout de suite, au prix du moment."},
    "limite": {"libelle": "À cours limité", "prix": "Prix limite ($ CA)",
               "aide": "Exécuté seulement à ce prix ou mieux."},
    "stop": {"libelle": "Stop", "prix": "Prix de déclenchement ($ CA)",
             "aide": "Devient un ordre au marché quand le prix atteint ce seuil."},
}

CLASSES = {"liquidites": "Liquidités", "revenu_fixe": "Revenu fixe", "actions": "Actions",
           "alternatifs": "Titres alternatifs"}
DIMENSIONS = {"risque": "Risque", "diversification": "Diversification", "preferences": "Préférences"}
AIDE_DIMENSIONS = {
    "risque": "Les pertes possibles, d'après le passé.",
    "diversification": "Ne pas mettre tous ses œufs dans le même panier.",
    "preferences": "Les thèmes que vous voulez éviter ou rechercher.",
}
MESURES = {
    "ampleur": "pire baisse",
    "duree": "temps pour se remettre d'une baisse",
    "classe_liquidites": "part des liquidités",
    "classe_revenu_fixe": "part du revenu fixe",
    "classe_actions": "part des actions",
    "classe_alternatifs": "part des titres alternatifs",
    "crypto": "part des cryptoactifs",
    "plus_grosse_action": "plus grosse action",
    "plus_gros_fonds": "plus gros fonds",
    "plus_gros_secteur": "plus gros secteur",
}
SECTEURS = {
    "Communication Services": "Services de communication",
    "Consumer Discretionary": "Consommation discrétionnaire",
    "Consumer Staples": "Consommation de base",
    "Energy": "Énergie",
    "Financials": "Services financiers",
    "Health Care": "Santé",
    "Industrials": "Industrie",
    "Information Technology": "Technologies de l'information",
    "Utilities": "Services publics",
}
DIRECTIONS_TEXTE = {
    "reste_dans_la_politique": "Votre portefeuille reste dans votre politique.",
    "fait_sortir_de_la_politique": "Votre portefeuille sortirait de votre politique.",
    "hors_politique_rapproche": "Votre portefeuille est déjà hors politique ; l'ordre l'en rapproche.",
    "hors_politique_aggrave": "Votre portefeuille est déjà hors politique ; l'ordre aggrave l'écart.",
}
STATUTS_CONTRAINTE = {"violee": "non respectée", "respectee": "respectée", "signalee": "signalée",
                      "ignoree": "ignorée", "non_applicable": "sans objet"}
NIVEAUX = {"essentiel": "essentiel", "standard": "standard", "detaille": "détaillé"}
SOURCES_LOCALES = {"questionnaire": "Votre réponse au questionnaire"}


# ---------------------------------------------------------------- références

@st.cache_data
def charger_reference(nom: str) -> dict:
    return references.charger(nom)  # bucket S3 privé s'il est configuré, sinon dossier reference/


QUESTIONNAIRE = charger_reference("questionnaire")
THEMES = {t["id"]: t["libelle"] for t in charger_reference("themes")["themes"]}
CHAMPS_Q = ("objectif", "horizon", "fluctuations", "capacite_perte", "besoin_liquidite", "experience")
PERSONAS = charger_reference("personas")["personas"]


@st.cache_data
def instruments() -> dict:
    r = api.lister_instruments()
    return {i["symbole"]: i for i in r.get("instruments", [])}


@st.cache_data
def derniers_prix_cad() -> dict:
    """Dernier prix connu de chaque titre, en dollars canadiens (lecture seule des données du moteur)."""
    try:
        from moteur import donnees
        p = donnees.prix_cad()
        return {t: float(v) for t, v in p.ffill().iloc[-1].items() if pd.notna(v)}
    except Exception:
        return {}


# ---------------------------------------------------------------- formats

def nombre(x: float, d: int = 1) -> str:
    texte = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return texte.replace("-", "−")


def pct(x: float, d: int = 1) -> str:
    """x est déjà en % (15 = 15 %)."""
    return f"{nombre(x, d)} %"


def pct_frac(x: float, d: int = 1) -> str:
    """x est une fraction (−0,18 = −18 %)."""
    return pct(x * 100, d)


def dollars(x: float, d: int = 0) -> str:
    return f"{nombre(x, d)} $"


def note_txt(x: float | None) -> str:
    return "—" if x is None else nombre(x, 0)


def libelle_option(champ: str, cle: str) -> str:
    opt = QUESTIONNAIRE[champ]["options"][cle]
    return opt if isinstance(opt, str) else opt["libelle"]


def libelle_theme_reponse(cle: str) -> str:
    return QUESTIONNAIRE["echelle_themes"]["options"][cle]["libelle"]


def libelle_mesure(dimension: str, cle: str) -> str:
    if dimension == "preferences":
        if cle in MESURES_OPERATION:
            return MESURES_OPERATION[cle]
        return f"thème « {THEMES.get(cle, cle)} »"
    return MESURES.get(cle, cle)


def nom_instrument(ticker: str) -> str:
    i = instruments().get(ticker)
    return f"{ticker} ({i['nom']})" if i else ticker


def secteur_fr(s: str) -> str:
    return SECTEURS.get(s, s)


def decrire_mesure(dimension: str, cle: str, m: dict) -> str:
    """Une phrase courte avec les chiffres d'une mesure, tels que le moteur les donne."""
    if cle == "ampleur" and dimension == "risque":
        return (f"pire baisse passée {pct_frac(m['pire_baisse'])} ; "
                f"limite du profil {pct_frac(m['pire_baisse_limite'])}")
    if cle == "duree" and dimension == "risque":
        texte = (f"{nombre(m['temps_sous_l_eau_annees'])} ans pour se remettre, "
                 f"pour un horizon de {nombre(m['horizon_annees'], 0)} ans")
        if m.get("non_recupere"):
            texte += " ; pas encore remis"
        return texte
    if cle.startswith("classe_"):
        return (f"{pct(m['poids'])} ; permis : {nombre(m['min'], 0)} à "
                f"{pct(m['max'], 0)}")
    if cle == "crypto" and dimension == "diversification":
        return f"{pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if cle in ("plus_grosse_action", "plus_gros_fonds"):
        if not m.get("ticker"):
            return "aucune"
        return f"{m['ticker']} : {pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if cle == "plus_gros_secteur":
        if not m.get("secteur"):
            return "aucune action seule"
        return f"{secteur_fr(m['secteur'])} : {pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if dimension == "preferences":
        if m.get("operation") and "poids_expose" in m:
            return f"{pct(m['poids_expose'])} du portefeuille ; repère de 15 %"
        if "poids_expose" in m:
            texte = f"{pct(m['poids_expose'])} du portefeuille dans ce thème à éviter"
            if m.get("etiquette_indeterminee"):
                texte += " (inconnu pour " + ", ".join(m["etiquette_indeterminee"]) + ")"
            return texte
        if "poids_vendu" in m:
            return f"{pct(m['poids_vendu'])} vendu dans ce thème recherché"
    return m.get("libelle", "")


def pourquoi_simple(sim: dict) -> str:
    """Une phrase claire qui dit pourquoi, à partir de la mesure qui donne le score."""
    if sim["verdict"]["code"] == "incompatible":
        detail = sim["contraintes_strictes"].get("detail", [])
        ce = (sim.get("operation") or {}).get("controle_experience", {})
        if any(d.get("controle") == "experience_operation" and d["statut"] == "violee" for d in detail):
            return (f"La {sim['operation']['libelle'].lower()} est exclue pour l'expérience "
                    f"« {libelle_option('experience', ce.get('experience', 'debutante'))} ». "
                    "C'est une règle stricte.")
        violees = [THEMES.get(d["theme"], d["theme"]) for d in detail if d["statut"] == "violee"]
        if violees:
            return (f"Ce titre touche un thème que vous excluez : {', '.join(violees)}. "
                    "C'est une règle stricte de votre fiche.")
        return "Une règle stricte de votre fiche n'est pas respectée."
    dim, mes = sim["dimension_min"], sim["mesure_min"]
    m = sim["apres"]["notes"][dim]["mesures"].get(mes, {})
    score = sim["score"]
    if mes == "ampleur":
        verbe = "dépasserait" if score < LIMITE else "resterait sous"
        return (f"Dans le passé, la pire baisse du portefeuille aurait été de {pct_frac(m['pire_baisse'], 0)}. "
                f"Elle {verbe} la limite de votre profil ({pct_frac(m['pire_baisse_limite'], 0)}).")
    if mes == "duree":
        return (f"Après une baisse, le portefeuille aurait mis {nombre(m['temps_sous_l_eau_annees'])} ans "
                f"à se remettre, pour un horizon de {nombre(m['horizon_annees'], 0)} ans.")
    if dim == "preferences":
        return f"Point le plus faible : {libelle_mesure(dim, mes)} — {decrire_mesure(dim, mes, m)}."
    return f"Point le plus faible : {libelle_mesure(dim, mes)} — {decrire_mesure(dim, mes, m)}."


def mesures_a_plat(bloc: dict) -> dict:
    """{(dimension, mesure): note} pour comparer deux inspections."""
    sortie = {}
    for dim, n in bloc.get("notes", {}).items():
        for cle, m in n.get("mesures", {}).items():
            if isinstance(m, dict) and "note" in m:
                sortie[(dim, cle)] = m["note"]
    return sortie


# ---------------------------------------------------------------- éléments visuels

def jauge(note: float | None, avant: float | None = None, hauteur: int = 10) -> str:
    """Barre 0 à 100 avec un repère à 50 (la limite). Une marque grise montre la valeur d'avant."""
    if note is None:
        return ""
    n = max(0.0, min(100.0, float(note)))
    couleur = COULEURS_VERDICT["compatible"] if note >= LIMITE else COULEURS_VERDICT["en_tension"]
    marque = ""
    if avant is not None:
        a = max(0.0, min(100.0, float(avant)))
        marque = (f'<div title="avant" style="position:absolute;left:calc({a}% - 1px);top:-3px;width:2px;'
                  f'height:{hauteur + 6}px;background:#8a8f94;"></div>')
    return (f'<div style="position:relative;height:{hauteur}px;background:#E6E2DE;border-radius:{hauteur}px;'
            f'margin:4px 0 2px 0;">'
            f'<div style="width:{n}%;height:100%;background:{couleur};border-radius:{hauteur}px;"></div>'
            f'<div title="limite 50" style="position:absolute;left:50%;top:-4px;width:2px;height:{hauteur + 8}px;'
            f'background:{MARINE};"></div>{marque}</div>')


def ligne_note(titre: str, note: float | None, avant: float | None = None, aide: str = "") -> None:
    if note is None:
        st.markdown(f"**{titre}** · sans objet")
        return
    valeur = f"{note_txt(avant)} → **{note_txt(note)}**" if avant is not None else f"**{note_txt(note)}**"
    st.markdown(f"**{titre}** · {valeur} / 100", help=aide or None)
    st.markdown(jauge(note, avant), unsafe_allow_html=True)


def legende_jauge(avec_avant: bool = False) -> None:
    texte = "Trait foncé : limite de 50. Sous 50, la politique n'est plus respectée."
    if avec_avant:
        texte += " Trait gris : avant l'ordre."
    st.caption(texte)


# ---------------------------------------------------------------- état de session

def cle_q(persona: str, champ: str) -> str:
    return f"q_{persona}_{champ}"


def nouveau_client() -> dict:
    """Une fiche vide et un portefeuille entièrement en liquidités, à composer à l'écran."""
    return {"id": NOUVEAU, "nom": "Nouveau client", "exemple": False, "valeur": VALEUR_NOUVEAU,
            "description": "Client créé à l'écran : réponses et portefeuille choisis par vous.",
            "questionnaire": {**REPONSES_PAR_DEFAUT, "themes": {t: "neutre" for t in THEMES}},
            "portefeuille_pct": {references.encaisse(): 100.0}, "ordre_demo": None}


def client_de_depart(cid: str) -> dict:
    """Le client tel qu'enregistré au départ : un exemple de l'énoncé, ou le nouveau client vierge."""
    for e in EXEMPLES_ENREGISTRES:
        if e["id"] == cid:
            p = PERSONAS[cid]
            return {"id": cid, "nom": p["nom"], "exemple": True, "valeur": e["valeur"],
                    "description": e["description"], "questionnaire": copy.deepcopy(p["questionnaire"]),
                    "portefeuille_pct": dict(p["portefeuille_pct"]), "ordre_demo": p.get("ordre_demo")}
    return nouveau_client()


def clients() -> dict:
    """Les clients de la session : les exemples enregistrés, puis le nouveau client. Tous de la même forme."""
    if "clients" not in st.session_state:
        ids = [e["id"] for e in EXEMPLES_ENREGISTRES] + [NOUVEAU]
        st.session_state["clients"] = {cid: client_de_depart(cid) for cid in ids}
    return st.session_state["clients"]


def client_enregistre(cid: str) -> dict:
    return clients()[cid]


def valeur_pf(persona: str) -> float:
    return float(client_enregistre(persona)["valeur"])


def initialiser(persona: str) -> None:
    p = client_enregistre(persona)
    q = p["questionnaire"]
    for champ in CHAMPS_Q:
        st.session_state.setdefault(cle_q(persona, champ), q[champ])
    for theme in THEMES:
        st.session_state.setdefault(cle_q(persona, "theme_" + theme), q["themes"].get(theme, "neutre"))
    st.session_state.setdefault(f"pf_{persona}", {t: float(w) for t, w in p["portefeuille_pct"].items()})
    st.session_state.setdefault(f"ordres_{persona}", [])
    ordre = p.get("ordre_demo") or {}
    st.session_state.setdefault(f"o_{persona}_ticker", ordre.get("ticker", "XIU.TO"))
    st.session_state.setdefault(f"o_{persona}_operation", ordre.get("sens", "achat"))
    st.session_state.setdefault(f"o_{persona}_type", "marche")
    st.session_state.setdefault(f"o_{persona}_montant",
                                round(float(ordre.get("pourcentage", 5)) * valeur_pf(persona) / 100, 2))


def reinitialiser(persona: str) -> None:
    for cle in list(st.session_state.keys()):
        if cle.startswith((f"q_{persona}_", f"pf_{persona}", f"o_{persona}_", f"ordres_{persona}", f"nc_{persona}_",
                           f"rapport_{persona}", f"precedent_{persona}", f"message_{persona}")):
            del st.session_state[cle]
    clients()[persona] = client_de_depart(persona)


def fiche_session(persona: str) -> dict:
    """La fiche envoyée au moteur et à l'agent : la même forme pour tout client."""
    s = st.session_state
    return {
        "id": persona,
        "nom": client_enregistre(persona)["nom"],
        "questionnaire": {
            "objectif": s[cle_q(persona, "objectif")],
            "horizon": s[cle_q(persona, "horizon")],
            **{c: s[cle_q(persona, c)] for c in CHAMPS_Q if c not in ("objectif", "horizon")},
            "themes": {t: s[cle_q(persona, "theme_" + t)] for t in THEMES},
        },
        "portefeuille_pct": dict(s[f"pf_{persona}"]),
    }


def fiche_modifiee(persona: str, fiche: dict) -> list[str]:
    """Libellés des réponses qui diffèrent de la fiche enregistrée du client."""
    q0 = client_enregistre(persona)["questionnaire"]
    q = fiche["questionnaire"]
    ecarts = []
    for champ in CHAMPS_Q:
        if q[champ] != q0[champ]:
            ecarts.append(f"{QUESTIONNAIRE[champ]['libelle']} : {libelle_option(champ, q[champ])}")
    for t in THEMES:
        if q["themes"][t] != q0["themes"].get(t, "neutre"):
            ecarts.append(f"{THEMES[t]} : {libelle_theme_reponse(q['themes'][t])}")
    return ecarts


def ecarts_questionnaire(q_avant: dict, q_apres: dict) -> list[str]:
    ecarts = []
    for champ in CHAMPS_Q:
        if q_avant[champ] != q_apres[champ]:
            ecarts.append(f"{QUESTIONNAIRE[champ]['libelle']} : {libelle_option(champ, q_avant[champ])} "
                          f"→ {libelle_option(champ, q_apres[champ])}")
    for t in THEMES:
        if q_avant["themes"][t] != q_apres["themes"][t]:
            ecarts.append(f"{THEMES[t]} : {libelle_theme_reponse(q_avant['themes'][t])} "
                          f"→ {libelle_theme_reponse(q_apres['themes'][t])}")
    return ecarts


# ---------------------------------------------------------------- inspection

def resume_appel(outil: str, r: dict) -> str:
    if "erreur" in r:
        return f"Erreur : {r['erreur']}"
    if outil == "lire_fiche_client":
        d = r["deduit"]
        return (f"Profil {d['profil']['libelle']}, horizon {nombre(d['horizon_annees']['valeur'], 0)} ans, "
                f"{len(d['contraintes_strictes']['valeur'])} règle(s) stricte(s), "
                f"{len(d['preferences_souples']['valeur'])} préférence(s).")
    if outil == "lire_fiche_instrument":
        vraies = [THEMES.get(k, k) for k, e in r.get("etiquettes", {}).items() if e.get("valeur") is True]
        return (f"{r['nom']}, {CLASSES.get(r['classe_politique'], r['classe_politique']).lower()}, "
                f"volatilité {pct_frac(r['statistiques_cad']['volatilite_annualisee'])} ; "
                f"thèmes : {', '.join(vraies) if vraies else 'aucun'}.")
    if outil == "simuler_ordre":
        return (f"« {r['verdict']['libelle']} », score {note_txt(r['avant']['score'])} → "
                f"{note_txt(r['apres']['score'])}, donné par {libelle_mesure(r['dimension_min'], r['mesure_min'])}.")
    if outil == "chercher_taille_compatible":
        if not r.get("lancee", True):
            return f"Recherche non lancée : {r.get('raison', '')}"
        if r.get("taille_compatible_pct") is None:
            return "Aucune taille compatible jusqu'au montant demandé."
        return f"Taille compatible : {pct(r['taille_compatible_pct'])}."
    return ""


def inspecter_moteur(persona: str, fiche: dict, ticker: str, sens: str, pourcentage: float,
                     details_ordre: dict | None = None) -> dict:
    """Le rapport structuré, appelé directement sur moteur.api, avec la trace des appels."""
    trace = []
    enregistre = client_enregistre(persona)
    client_affiche = persona if not fiche_modifiee(persona, fiche) and \
        fiche["portefeuille_pct"] == {t: float(w) for t, w in enregistre["portefeuille_pct"].items()} \
        else f"fiche de session ({enregistre['nom']})"

    def appel(outil, fonction, *args, **arguments):
        debut = time.perf_counter()
        r = fonction(*args)
        trace.append({"etape": len(trace) + 1, "outil": outil, "arguments": arguments,
                      "resultat_resume": resume_appel(outil, r), "resultat": r,
                      "duree_s": time.perf_counter() - debut})
        return r

    fiche_client = appel("lire_fiche_client", api.lire_fiche_client, fiche, client=client_affiche)
    fiche_instr = appel("lire_fiche_instrument", api.lire_fiche_instrument, ticker, ticker=ticker)
    op = operation_moteur((details_ordre or {}).get("operation"))
    arg_op = {"operation": op} if op != "comptant" else {}
    simulation = appel("simuler_ordre", api.simuler_ordre, fiche, ticker, sens, pourcentage, op,
                       client=client_affiche, ticker=ticker, sens=sens, pourcentage=pourcentage, **arg_op)
    taille = None
    if "erreur" not in simulation:
        taille = appel("chercher_taille_compatible", api.chercher_taille_compatible, fiche, ticker, sens,
                       pourcentage, op, client=client_affiche, ticker=ticker, sens=sens, pourcentage=pourcentage,
                       **arg_op)
    return {
        "ordre": {"ticker": ticker, "sens": sens, "pourcentage": pourcentage, **(details_ordre or {})},
        "fiche": copy.deepcopy(fiche),
        "fiche_client": fiche_client,
        "fiche_instrument": fiche_instr,
        "simulation": simulation,
        "taille": taille,
        "trace_moteur": trace,
        "agent": None,  # rempli juste après l'affichage du rapport structuré
    }


def accepte_sur_etape(fonction) -> bool:
    """Vrai si l'agent sait annoncer ses étapes (paramètre `sur_etape`)."""
    try:
        return "sur_etape" in inspect.signature(fonction).parameters
    except (TypeError, ValueError):
        return False


def appeler_agent(fiche: dict, ticker: str, sens: str, pourcentage: float, operation: str = "comptant",
                  sur_etape=None) -> dict:
    """Appelle l'agent s'il existe ; renvoie toujours un dict {explication, trace, erreur, ...}."""
    try:
        from agent.inspection import inspecter  # import paresseux : le module peut être absent
    except Exception:
        return {"explication": None, "trace": [], "erreur": "module de l'agent absent"}
    options = {"operation": operation}
    if sur_etape is not None and accepte_sur_etape(inspecter):
        options["sur_etape"] = sur_etape
    try:
        r = inspecter(copy.deepcopy(fiche), ticker, sens, pourcentage, **options)
    except Exception as exc:  # l'agent ne doit jamais faire tomber le rapport
        return {"explication": None, "trace": [], "erreur": f"l'agent a échoué ({type(exc).__name__})"}
    if not isinstance(r, dict):
        return {"explication": None, "trace": [], "erreur": "réponse de l'agent illisible"}
    r.setdefault("trace", [])
    if not r.get("erreur") and not r.get("explication"):
        r["erreur"] = "aucune explication reçue"
    return r


# ---------------------------------------------------------------- graphiques

def graphique_anneau(df: pd.DataFrame, categorie: str, couleurs: dict | list, titre: str) -> alt.Chart:
    df = df.sort_values("pct", ascending=False).copy()
    if isinstance(couleurs, dict):
        couleurs = {f"{c} · {pct(float(df.loc[df[categorie] == c, 'pct'].sum()), 0)}": v
                    for c, v in couleurs.items() if c in set(df[categorie])}
    df[categorie] = [f"{c} · {pct(w, 0)}" for c, w in zip(df[categorie], df["pct"])]
    if isinstance(couleurs, dict):
        domaine = [c for c in couleurs if c in set(df[categorie])]
        echelle = alt.Scale(domain=domaine, range=[couleurs[c] for c in domaine])
    else:
        domaine = list(df[categorie])
        echelle = alt.Scale(domain=domaine, range=(couleurs * 3)[:len(domaine)])
    return alt.Chart(df).mark_arc(innerRadius=62, outerRadius=110, stroke="white", strokeWidth=1.5).encode(
        theta=alt.Theta("pct:Q", stack=True),
        color=alt.Color(f"{categorie}:N", scale=echelle, sort=domaine,
                        legend=alt.Legend(title=None, orient="right", labelFontSize=13, rowPadding=2,
                                          columns=1 if len(domaine) <= 6 else 2, columnPadding=12,
                                          symbolSize=110, symbolType="circle", labelLimit=200)),
        order=alt.Order("pct:Q", sort="descending"),
        tooltip=[alt.Tooltip(f"{categorie}:N", title=titre), alt.Tooltip("pct:Q", title="Part (%)", format=".1f"),
                 alt.Tooltip("montant:N", title="Montant")],
    ).properties(height=260, title=alt.TitleParams(titre, anchor="start", fontSize=15, color=MARINE))


def graphique_classes(poids: dict, fourchettes: dict) -> alt.Chart:
    lignes = []
    for cle, lib in CLASSES.items():
        f = fourchettes[cle]
        p = float(poids.get(cle, 0.0))
        lignes.append({"classe": lib, "poids": p, "min": f["min"], "max": f["max"], "cible": f["cible"],
                       "etat": "Dans la zone permise" if f["min"] <= p <= f["max"] else "Hors de la zone"})
    df = pd.DataFrame(lignes)
    ordre = list(CLASSES.values())
    y = alt.Y("classe:N", sort=ordre, title=None, axis=alt.Axis(labelFontSize=12))
    bande = alt.Chart(df).mark_bar(color="#A8C1B8", opacity=0.45, size=26).encode(
        y=y, x=alt.X("min:Q", title="Part du portefeuille (%)", scale=alt.Scale(domain=[0, 100])),
        x2="max:Q",
        tooltip=[alt.Tooltip("classe:N", title="Classe"), alt.Tooltip("min:Q", title="Minimum (%)"),
                 alt.Tooltip("max:Q", title="Maximum (%)")])
    barre = alt.Chart(df).mark_bar(size=10).encode(
        y=y, x="poids:Q",
        color=alt.Color("etat:N", scale=alt.Scale(domain=["Dans la zone permise", "Hors de la zone"],
                                                  range=[MARINE, COULEURS_VERDICT["en_tension"]]),
                        legend=None),
        tooltip=[alt.Tooltip("classe:N", title="Classe"), alt.Tooltip("poids:Q", title="Part (%)", format=".1f")])
    return (bande + barre).properties(height=210)


def graphique_courbe(taille: dict, valeur: float) -> alt.Chart:
    df = pd.DataFrame(taille["courbe"])
    df["dimension"] = df["dimension_min"].map(lambda d: DIMENSIONS.get(d, d))
    df["mesure"] = [libelle_mesure(d, m) for d, m in zip(df["dimension_min"], df["mesure_min"])]
    df["montant"] = [dollars(t * valeur / 100) for t in df["taille_pct"]]
    haut = max(100.0, float(df["score"].max()))
    base = alt.Chart(df).encode(
        x=alt.X("taille_pct:Q", title="Taille de l'ordre (% du portefeuille)",
                scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1, format="d")),
        y=alt.Y("score:Q", title="Score après l'ordre", scale=alt.Scale(domain=[0, haut])),
        tooltip=[alt.Tooltip("montant:N", title="Montant"),
                 alt.Tooltip("taille_pct:Q", title="Part (%)", format=".1f"),
                 alt.Tooltip("score:Q", title="Score", format=".0f"),
                 alt.Tooltip("mesure:N", title="Donné par")])
    zone = alt.Chart(pd.DataFrame({"y": [0], "y2": [LIMITE]})).mark_rect(
        color=COULEURS_VERDICT["en_tension"], opacity=0.07).encode(y="y:Q", y2="y2:Q")
    ligne = base.mark_line(color=MARINE, strokeWidth=2) + base.mark_circle(size=30, color=MARINE)
    limite = alt.Chart(pd.DataFrame({"y": [LIMITE]})).mark_rule(color=MARINE, strokeDash=[5, 4]).encode(y="y:Q")
    x_min, x_max = float(df["taille_pct"].min()), float(df["taille_pct"].max())
    lim = pd.DataFrame({"y": [LIMITE], "x": [x_min], "lib": ["Limite : 50"]})
    couches = [zone, ligne, limite] + _etiquette(lim, MARINE, align="left", dy=12)
    if taille.get("taille_compatible_pct") is not None:
        x_tc = float(taille["taille_compatible_pct"])
        tc = pd.DataFrame({"x": [x_tc], "y": [haut * 0.94],
                           "lib": [f"Jusqu'ici : compatible ({dollars(x_tc * valeur / 100)})"]})
        couches.append(alt.Chart(tc).mark_rule(color=COULEURS_VERDICT["compatible"], strokeWidth=2).encode(x="x:Q"))
        a_gauche = x_tc > (x_min + x_max) / 2
        couches += _etiquette(tc, COULEURS_VERDICT["compatible"], align="right" if a_gauche else "left",
                              dx=-6 if a_gauche else 6)
    return alt.layer(*couches).properties(height=260)


def _etiquette(df: pd.DataFrame, couleur: str, **pos) -> list:
    enc = {"x": "x:Q", "y": "y:Q", "text": "lib:N"}
    halo = alt.Chart(df).mark_text(fontSize=12, stroke="white", strokeWidth=4, **pos).encode(**enc)
    texte = alt.Chart(df).mark_text(fontSize=12, color=couleur, **pos).encode(**enc)
    return [halo, texte]


# ---------------------------------------------------------------- rendu : fiche

def libelle_source(source_id: str, sources: dict) -> str:
    if source_id in SOURCES_LOCALES:
        return SOURCES_LOCALES[source_id]
    s = sources.get(source_id)
    if not s:
        return source_id
    if s["nature"] == "publie":
        return f"Publié par {s['source']}"
    return f"Hypothèse : {s['libelle']}"


def valeur_deduite(cle: str, e: dict) -> str:
    v = e["valeur"]
    if cle == "profil":
        return e.get("libelle", v)
    if cle == "horizon_annees":
        return f"{nombre(v, 0)} ans"
    if cle == "plafonds_concentration_pct":
        return (f"{pct(v['action_individuelle'], 0)} par action, {pct(v['secteur'], 0)} par secteur, "
                f"{pct(v['fonds_negocie_en_bourse'], 0)} par fonds")
    if cle == "crypto_pct":
        return f"cible {pct(v['cible_pct'], 1)}, maximum {pct(v['plafond_pct'], 1)}"
    if cle == "contraintes_strictes":
        if not v:
            return "aucune"
        return " ; ".join(f"{libelle_theme_reponse(c['reponse'])} : {THEMES.get(c['theme'], c['theme'])}"
                          if isinstance(c, dict) else str(c) for c in v)
    if cle == "preferences_souples":
        if not v:
            return "aucune"
        return " ; ".join(f"{libelle_theme_reponse(c['reponse'])} : {THEMES.get(c['theme'], c['theme'])}"
                          for c in v)
    if cle == "besoin_liquidite_pct":
        return e.get("phrase", f"{nombre(v, 0)} %")
    if cle == "niveau_detail":
        return NIVEAUX.get(v, v)
    if cle == "coherence_objectif":
        return {"coherent": "cohérent avec le profil", "a_verifier": "à vérifier"}.get(v, v)
    return str(v)


LIBELLES_DEDUIT = {
    "profil": "Profil d'investisseur",
    "fourchettes_pct": "Zones permises par classe",
    "besoin_liquidite_pct": "Liquidités de l'année",
    "horizon_annees": "Horizon utilisé",
    "plafonds_concentration_pct": "Maximum par titre",
    "crypto_pct": "Cryptoactifs",
    "contraintes_strictes": "Règles strictes",
    "preferences_souples": "Préférences",
    "niveau_detail": "Détail du rapport",
    "coherence_objectif": "Objectif et profil",
}


def onglet_fiche(persona: str, fiche_client: dict) -> None:
    gauche, droite = st.columns([1.15, 1], gap="large")
    with gauche:
        st.subheader("Vos réponses")
        st.caption("Changez une réponse : tout le reste se met à jour.")
        enregistre = client_enregistre(persona)
        if enregistre["exemple"]:
            q0 = enregistre["questionnaire"]
            st.caption(f"Les réponses de départ de {enregistre['nom']} sont fictives (hypothèse du projet). "
                       f"Capacité à supporter une perte : même niveau que les fluctuations acceptées ; "
                       f"besoin de liquidités : « {libelle_option('besoin_liquidite', q0['besoin_liquidite'])} ».")
        else:
            st.info("Nouveau client : choisissez chaque réponse. Les choix affichés au départ sont des "
                    "réponses par défaut, pas les vôtres.")
        c1, c2 = st.columns(2)
        for i, champ in enumerate(CHAMPS_Q):
            options = list(QUESTIONNAIRE[champ]["options"])
            (c1 if i % 2 == 0 else c2).selectbox(
                QUESTIONNAIRE[champ]["libelle"], options, key=cle_q(persona, champ),
                format_func=lambda o, c=champ: libelle_option(c, o))
        st.markdown("**Thèmes**")
        st.caption("« Exclure » et « Obligatoire » sont des règles strictes. Les autres choix sont des préférences.")
        echelle = list(QUESTIONNAIRE["echelle_themes"]["options"])
        for t, lib in THEMES.items():
            st.radio(lib, echelle, key=cle_q(persona, "theme_" + t), horizontal=True,
                     format_func=libelle_theme_reponse)

    with droite:
        st.subheader("Ce que l'outil en déduit")
        if "erreur" in fiche_client:
            st.error(fiche_client["erreur"])
            return
        sources = {s["id"]: s for s in fiche_client.get("sources", [])}
        for cle, e in fiche_client["deduit"].items():
            lib = LIBELLES_DEDUIT.get(cle, cle)
            origine = libelle_source(e.get("source", ""), sources)
            if e.get("regle"):
                origine += " · " + libelle_source(e["regle"], sources)
            if e.get("hypothese"):
                origine += " · " + libelle_source(e["hypothese"], sources)
            if cle == "profil" and e.get("phrase"):
                st.markdown(f"**{lib}** : {valeur_deduite(cle, e)}")
                st.markdown(e["phrase"])
            elif cle == "fourchettes_pct":
                st.markdown(f"**{lib}**")
                df = pd.DataFrame([{"Classe": CLASSES[c], "Minimum (%)": f["min"], "Cible (%)": f["cible"],
                                    "Maximum (%)": f["max"]} for c, f in e["valeur"].items()])
                st.dataframe(df, hide_index=True, width="stretch")
            else:
                st.markdown(f"**{lib}** : {valeur_deduite(cle, e)}")
            st.caption(origine)


# ---------------------------------------------------------------- rendu : portefeuille

def ajouter_position(persona: str) -> None:
    """Ajoute au portefeuille le montant choisi, pris sur les liquidités. Refuse de dépasser la valeur totale."""
    s = st.session_state
    cash = references.encaisse()
    valeur = valeur_pf(persona)
    ticker, montant = s[f"nc_{persona}_titre"], float(s[f"nc_{persona}_montant"] or 0)
    pf = dict(s[f"pf_{persona}"])
    dispo = pf.get(cash, 0.0) * valeur / 100
    if montant <= 0:
        s[f"nc_{persona}_message"] = ("erreur", "Indiquez un montant plus grand que 0 $.")
    elif montant > dispo + 0.005:
        s[f"nc_{persona}_message"] = ("erreur", f"Refusé : le total dépasserait la valeur du portefeuille. "
                                                f"Il reste {dollars(dispo)} à placer.")
    else:
        part = montant / valeur * 100
        pf[cash] = pf.get(cash, 0.0) - part
        pf[ticker] = pf.get(ticker, 0.0) + part
        s[f"pf_{persona}"] = {t: w for t, w in pf.items() if abs(w) > 1e-9}
        s[f"nc_{persona}_message"] = ("ok", f"{dollars(montant)} de {ticker} ajoutés.")
    s.pop(f"rapport_{persona}", None)


def changer_valeur(persona: str) -> None:
    """Nouvelle valeur totale : les montants placés restent les mêmes en dollars, les liquidités font le reste."""
    s = st.session_state
    cash = references.encaisse()
    ancienne, nouvelle = valeur_pf(persona), float(s[f"nc_{persona}_valeur"])
    places = {t: w * ancienne / 100 for t, w in s[f"pf_{persona}"].items() if t != cash}
    if sum(places.values()) > nouvelle + 0.005:
        s[f"nc_{persona}_valeur"] = ancienne
        s[f"nc_{persona}_message"] = ("erreur", f"Refusé : les positions placées ({dollars(sum(places.values()))}) "
                                                "dépassent cette valeur.")
        return
    pf = {t: m / nouvelle * 100 for t, m in places.items()}
    pf[cash] = 100 - sum(pf.values())
    s[f"pf_{persona}"] = {t: w for t, w in pf.items() if abs(w) > 1e-9}
    client_enregistre(persona)["valeur"] = nouvelle
    s.pop(f"rapport_{persona}", None)


def vider_portefeuille(persona: str) -> None:
    st.session_state[f"pf_{persona}"] = {references.encaisse(): 100.0}
    st.session_state.pop(f"rapport_{persona}", None)


def composer_portefeuille(persona: str) -> None:
    """Composer le portefeuille à l'écran : la valeur totale, puis chaque position et son montant."""
    s = st.session_state
    cash = references.encaisse()
    univers = instruments()
    pf = s[f"pf_{persona}"]
    # Ouvert pour un client créé à l'écran ; replié pour un exemple, qui a déjà son portefeuille.
    ouvert = not client_enregistre(persona)["exemple"] or set(pf) == {cash}
    with st.expander("Composer le portefeuille", expanded=ouvert):
        s.setdefault(f"nc_{persona}_valeur", float(valeur_pf(persona)))
        st.number_input("Valeur totale du portefeuille ($ CA)", min_value=1_000.0, step=1_000.0, format="%.0f",
                        key=f"nc_{persona}_valeur", on_change=changer_valeur, args=(persona,))
        c1, c2, c3 = st.columns([2, 1.2, 1])
        c1.selectbox("Titre", [t for t in univers if t != cash], key=f"nc_{persona}_titre",
                     format_func=lambda t: f"{t} — {univers[t]['nom']}")
        c2.number_input("Montant ($ CA)", min_value=0.0, step=1_000.0, value=10_000.0, format="%.0f",
                        key=f"nc_{persona}_montant")
        c3.markdown("&nbsp;")
        c3.button("Ajouter", key=f"nc_{persona}_ajouter", on_click=ajouter_position, args=(persona,),
                  width="stretch")
        dispo = pf.get(cash, 0.0) * valeur_pf(persona) / 100
        st.caption(f"Ce qui n'est pas placé reste en liquidités ({cash}) : {dollars(dispo)}, "
                   f"{pct(pf.get(cash, 0.0))} du portefeuille.")
        message = s.pop(f"nc_{persona}_message", None)
        if message:
            (st.success if message[0] == "ok" else st.error)(message[1])
        st.button("Tout remettre en liquidités", key=f"nc_{persona}_vider", on_click=vider_portefeuille,
                  args=(persona,))


def onglet_portefeuille(persona: str, fiche: dict, fiche_client: dict) -> None:
    composer_portefeuille(persona)
    if "erreur" in fiche_client:
        st.error(fiche_client["erreur"])
        return
    valeur = valeur_pf(persona)
    pf = fiche_client["portefeuille_pct"]
    univers = instruments()
    profil = fiche_client["deduit"]["profil"]["libelle"]

    nature = "montant fictif" if client_enregistre(persona)["exemple"] else "montant saisi"
    st.markdown(f"Valeur du portefeuille : **{dollars(valeur)}** ({nature}) · profil **{profil}**")
    ordres = st.session_state.get(f"ordres_{persona}", [])
    if ordres:
        st.caption(f"Tient compte de {len(ordres)} ordre(s) simulé(s) dans cette session.")

    # État des lieux en premier : le chiffre, la jauge, une phrase.
    e = api.etat_des_lieux(fiche)
    if "erreur" in e:
        st.error(e["erreur"])
    else:
        st.subheader("État des lieux")
        dans = e["dans_la_politique"]
        couleur = COULEURS_VERDICT["compatible"] if dans else COULEURS_VERDICT["en_tension"]
        statut = "Dans votre politique" if dans else "Hors de votre politique"
        st.markdown(f'<div style="font-size:1.15rem;"><b>Score : {note_txt(e["score"])} / 100</b> · '
                    f'<span style="color:{couleur};font-weight:600;">{statut}</span></div>',
                    unsafe_allow_html=True)
        st.markdown(jauge(e["score"], hauteur=12), unsafe_allow_html=True)
        cols = st.columns(3)
        for col, dim in zip(cols, ("risque", "diversification", "preferences")):
            n = e["notes"][dim]
            with col:
                if n.get("sans_objet"):
                    ligne_note(DIMENSIONS[dim], None)
                    st.caption("Aucun thème à éviter ou à rechercher.")
                    continue
                ligne_note(DIMENSIONS[dim], n["note"], aide=AIDE_DIMENSIONS[dim])
                m = n["mesures"].get(n["mesure_min"], {})
                if n["note"] >= 99.95:
                    st.caption("Sur la cible.")
                else:
                    st.caption(f"Point faible : {libelle_mesure(dim, n['mesure_min'])} — "
                               f"{decrire_mesure(dim, n['mesure_min'], m)}.")
        legende_jauge()

    st.subheader("Répartition")
    lignes = []
    for t, w in sorted(pf.items(), key=lambda x: -x[1]):
        lignes.append({"position": t, "nom": univers.get(t, {}).get("nom", ""),
                       "classe": CLASSES.get(univers.get(t, {}).get("classe_politique", ""), ""),
                       "pct": round(w, 2), "montant": dollars(w * valeur / 100)})
    df_pos = pd.DataFrame(lignes)
    df_cls = (df_pos.groupby("classe", as_index=False)["pct"].sum())
    df_cls["montant"] = [dollars(p * valeur / 100) for p in df_cls["pct"]]
    c1, c2 = st.columns(2)
    c1.altair_chart(graphique_anneau(df_pos, "position", COULEURS_POSITIONS, "Par titre"), width="stretch")
    c2.altair_chart(graphique_anneau(df_cls, "classe", COULEURS_CLASSES, "Par classe d'actif"), width="stretch")

    st.markdown(f"**Chaque classe face à la zone permise par le profil {profil}**")
    st.altair_chart(graphique_classes(fiche_client["poids_par_classe_pct"],
                                      fiche_client["deduit"]["fourchettes_pct"]["valeur"]), width="stretch")
    st.caption("Bande verte : zone permise. Barre : part actuelle (foncée si dans la zone, ambre sinon).")

    st.markdown("**Positions**")
    tableau = pd.DataFrame([{"Titre": l["position"], "Nom": l["nom"], "Classe": l["classe"],
                             "Montant": l["montant"], "Part": pct(l["pct"])} for l in lignes])
    st.dataframe(tableau, hide_index=True, width="stretch")
    if ordres:
        st.markdown("**Ordres simulés de la session**")
        st.dataframe(pd.DataFrame(ordres), hide_index=True, width="stretch")


# ---------------------------------------------------------------- rendu : rapport

def bloc_verdict(sim: dict, rapport: dict, valeur: float) -> None:
    v = sim["verdict"]
    code = v["code"]
    couleur, fond = COULEURS_VERDICT.get(code, MARINE), FONDS_VERDICT.get(code, GRIS_CHAUD)
    o = rapport["ordre"]
    nom_op = OPERATIONS.get(o.get("operation", o["sens"]), {}).get("nom", o["sens"].capitalize())
    montant = o.get("montant", o["pourcentage"] * valeur / 100)
    d = sim["direction"]
    st.markdown(
        f"""<div style="background:{fond};border-left:6px solid {couleur};border-radius:6px;padding:0.9rem 1.2rem;margin:0.4rem 0 0.8rem 0;">
<div style="font-size:0.95rem;color:{MARINE};">{nom_op} de <b>{dollars(montant)}</b> de {nom_instrument(o['ticker'])} · {pct(o['pourcentage'])} du portefeuille</div>
<div style="font-size:1.9rem;font-weight:700;color:{couleur};line-height:1.3;">{v['libelle']}</div>
<div style="font-size:1.02rem;color:{MARINE};">{pourquoi_simple(sim)}</div>
</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.2])
    with c1:
        ligne_note("Score après l'ordre", sim["score"], sim["avant"]["score"],
                   aide="De 0 à 100. À partir de 50, l'ordre respecte votre politique.")
        legende_jauge(avec_avant=True)
    with c2:
        if code == "incompatible":
            st.markdown(f"**Notes seules : {d['libelle'].lower()}.** Une règle stricte passe avant le score.")
        else:
            st.markdown(f"**{d['libelle']}.** {DIRECTIONS_TEXTE.get(d['cas'], '')}")
            phrase_solidite(sim.get("solidite"))
        c = sim.get("contribution_risque_apres")
        if c and c.get("part_du_risque_pct") is not None:
            lien = "mais" if c["part_du_risque_pct"] > 1.25 * c["poids_pct"] else "et"
            if c["poids_pct"] < 0:  # vente à découvert
                st.markdown(f"La position à découvert sur {c['ticker']} ({pct(-c['poids_pct'], 0)} du portefeuille) "
                            f"porterait **{pct(c['part_du_risque_pct'], 0)} de son risque**.")
            else:
                st.markdown(f"{c['ticker']} ferait {pct(c['poids_pct'], 0)} du portefeuille, "
                            f"{lien} **{pct(c['part_du_risque_pct'], 0)} de son risque**.")


def bloc_operation(sim: dict) -> None:
    """Achat sur marge ou vente à découvert : le contrôle d'expérience et le levier, une phrase chacun."""
    op = sim.get("operation") or {}
    if op.get("code") in (None, "comptant"):
        return
    ce = op.get("controle_experience", {})
    exp = libelle_option("experience", ce.get("experience", "intermediaire"))
    nom = op["libelle"].lower()
    if ce.get("effet") == "contrainte_stricte":
        phrase = f"Votre expérience ({exp}) exclut la {nom}."
    elif ce.get("effet") == "preference_souple":
        phrase = f"Votre expérience ({exp}) : la {nom} est à éviter. Note : {note_txt(ce.get('note'))} sur 100."
    else:
        phrase = f"Votre expérience ({exp}) : la {nom} ne change pas le score."
    st.markdown(f"**Expérience.** {phrase}")
    if op.get("levier_apres") is not None:
        st.markdown(f"**Levier : {nombre(op['levier_apres'], 2)}.** Votre exposition serait de "
                    f"{nombre(op['exposition_brute_apres_pct'], 0)} $ pour 100 $ qui vous appartiennent.")


SOLIDITE_TEXTE = {
    "solide": "le résultat est le même dans une année de forte baisse comme dans les autres.",
    "fragile": "le résultat change selon qu'on regarde une année de forte baisse ou les autres.",
}


def phrase_solidite(solidite: dict | None) -> None:
    if solidite and solidite.get("statut") in SOLIDITE_TEXTE:
        st.markdown(f"**{solidite['libelle']}** : {SOLIDITE_TEXTE[solidite['statut']]}")


def section_solidite(solidite: dict | None) -> None:
    if not solidite or not solidite.get("fenetres"):
        st.caption("Solidité non calculée.")
        return
    for f in solidite["fenetres"].values():
        cote = "respecte la politique" if f["dans_la_politique"] else "sous la limite de 50"
        st.markdown(f"- {f['libelle']} : score {note_txt(f['score'])}, {cote}.")
    st.caption(f"{solidite['explication']} Le score affiché plus haut reste celui de toute la période.")


def section_substitut(rapport: dict, valeur: float) -> None:
    """Le titre que l'agent a testé à la place de celui de l'ordre : une possibilité, pas une recommandation."""
    s = (rapport.get("agent") or {}).get("substitut")
    if not s or not s.get("verdict"):
        return
    code = s["verdict"].get("code")
    couleur = COULEURS_VERDICT.get(code, MARINE)
    pourcentage = s.get("pourcentage") or rapport["ordre"]["pourcentage"]
    st.markdown(f"L'agent a aussi testé un autre titre : le même montant ({dollars(pourcentage * valeur / 100)}) "
                f"en {nom_instrument(s['ticker'])} serait <b style=\"color:{couleur}\">{s['verdict']['libelle'].lower()}</b> "
                f"(score {note_txt(s.get('score'))}).", unsafe_allow_html=True)
    st.caption("Une possibilité testée, pas une recommandation.")


def section_possible(taille: dict | None, valeur: float) -> None:
    st.markdown("#### Ce qui est possible")
    if not taille or "erreur" in taille:
        st.markdown("La recherche d'une taille n'a pas pu être faite"
                    + (f" : {taille['erreur']}" if taille and "erreur" in taille else "."))
        return
    if not taille.get("lancee", True):
        st.markdown("Aucune taille n'est proposée. Changer le montant ne règle pas une règle stricte.")
        return
    issue = taille.get("issue")
    tc = taille.get("taille_compatible_pct")
    if issue == "compatible_tel_quel":
        st.markdown(f"L'ordre est compatible tel quel ({dollars(taille['taille_demandee_pct'] * valeur / 100)}).")
    elif issue == "compatible_avec_ajustement" and tc is not None:
        st.markdown(f"Jusqu'à **{dollars(tc * valeur / 100)}** ({pct(tc)} du portefeuille), "
                    "l'ordre serait compatible.")
    else:
        st.markdown(f"Aucun montant jusqu'à {dollars(taille['taille_demandee_pct'] * valeur / 100)} "
                    f"({pct(taille['taille_demandee_pct'])}) ne garde le score à {LIMITE} ou plus.")
    if taille.get("courbe"):
        st.altair_chart(graphique_courbe(taille, valeur), width="stretch")
        st.caption("Score selon le montant. La zone ombrée est sous la limite de 50.")


def bloc_changements(rapport: dict, precedent: dict | None) -> None:
    """Lecture avant/après entre deux inspections : ce qui a bougé et pourquoi."""
    if not precedent:
        return
    s0, s1 = precedent["simulation"], rapport["simulation"]
    if "erreur" in s0 or "erreur" in s1:
        return
    changements = ecarts_questionnaire(precedent["fiche"]["questionnaire"], rapport["fiche"]["questionnaire"])
    o0, o1 = precedent["ordre"], rapport["ordre"]
    if (o0["ticker"], o0["sens"], o0["pourcentage"], o0.get("operation")) != \
            (o1["ticker"], o1["sens"], o1["pourcentage"], o1.get("operation")):
        changements.insert(0, f"Ordre : {o0['sens']} {pct(o0['pourcentage'])} {o0['ticker']} → "
                              f"{o1['sens']} {pct(o1['pourcentage'])} {o1['ticker']}")
    if precedent["fiche"]["portefeuille_pct"] != rapport["fiche"]["portefeuille_pct"]:
        changements.append("Portefeuille modifié par un ordre simulé")
    if not changements:
        return
    a0, a1 = mesures_a_plat(s0["apres"]), mesures_a_plat(s1["apres"])
    lignes = []
    for cle in a1:
        if cle in a0 and abs(a1[cle] - a0[cle]) >= 0.05:
            lignes.append({"Note": DIMENSIONS[cle[0]], "Mesure": libelle_mesure(*cle),
                           "Avant": round(a0[cle]), "Maintenant": round(a1[cle])})
    with st.container(border=True):
        st.markdown(f"**{DEPUIS_PRECEDENT}**")
        st.markdown("Changé : " + " ; ".join(changements) + ".")
        st.markdown(f"{s0['verdict']['libelle']} → **{s1['verdict']['libelle']}** · score "
                    f"{note_txt(s0['score'])} → **{note_txt(s1['score'])}**")
        if lignes:
            st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
        else:
            st.markdown("Aucune mesure n'a bougé.")


def section_contraintes(sim: dict) -> None:
    cs = sim["contraintes_strictes"]
    if not cs.get("detail"):
        st.markdown("Aucune règle stricte dans votre fiche.")
        return
    for d in cs["detail"]:
        statut = STATUTS_CONTRAINTE.get(d["statut"], d["statut"])
        if d.get("controle") == "experience_operation":
            op = sim.get("operation") or {}
            exp = libelle_option("experience", op.get("controle_experience", {}).get("experience", "debutante"))
            st.markdown(f"- **{op.get('libelle', d['theme'])}** — exclue pour l'expérience « {exp} ».")
            continue
        theme = THEMES.get(d["theme"], d["theme"])
        texte = f"- **{libelle_theme_reponse(d['reponse'])} : {theme}** — {statut}."
        decl = d.get("declencheur") or {}
        if isinstance(decl, dict) and decl.get("preuve"):
            texte += f" Preuve : {decl['preuve']}"
        st.markdown(texte)


def section_notes(sim: dict, niveau: str) -> None:
    st.caption("Chaque note va de 0 à 100. Le score est la plus faible des trois.")
    cols = st.columns(3)
    for col, dim in zip(cols, ("risque", "diversification", "preferences")):
        n0, n1 = sim["avant"]["notes"][dim], sim["apres"]["notes"][dim]
        with col:
            if n1.get("sans_objet"):
                ligne_note(DIMENSIONS[dim], None)
                continue
            ligne_note(DIMENSIONS[dim], n1["note"], n0["note"], aide=AIDE_DIMENSIONS[dim])
            st.caption("Sur la cible." if n1["note"] >= 99.95
                       else f"Point faible : {libelle_mesure(dim, n1['mesure_min'])}.")
    legende_jauge(avec_avant=True)
    if niveau == "essentiel":
        return
    lignes = []
    for dim in ("risque", "diversification", "preferences"):
        n0, n1 = sim["avant"]["notes"][dim], sim["apres"]["notes"][dim]
        if n1.get("sans_objet"):
            continue
        for cle, m1 in n1["mesures"].items():
            if not isinstance(m1, dict) or "note" not in m1:
                continue
            m0 = n0["mesures"].get(cle, {})
            lignes.append({"Note": DIMENSIONS[dim], "Mesure": libelle_mesure(dim, cle),
                           "Avant": round(m0["note"]) if m0 and "note" in m0 else None,
                           "Après": round(m1["note"]), "Chiffres": decrire_mesure(dim, cle, m1)})
    st.markdown("**Toutes les mesures**")
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch",
                 column_config={"Après": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
    if niveau == "detaille":
        n0, n1 = sim["avant"]["notes"]["risque"], sim["apres"]["notes"]["risque"]
        st.caption(f"Volatilité du portefeuille (variation habituelle sur un an) : "
                   f"{pct_frac(n0['volatilite_annualisee'])} → {pct_frac(n1['volatilite_annualisee'])}. "
                   "Affichée, non notée.")
    for dim in ("risque", "diversification", "preferences"):
        for s in sim["apres"]["notes"][dim].get("signalements", []):
            st.markdown(f"- Signalement : {s.get('message', '')}")


def jambe_txt(o: dict, valeur: float) -> str:
    """« achat de 7,5 % de XIU.TO (3 750 $) »."""
    return (f"{o.get('sens', 'achat')} de {pct(o.get('pourcentage', 0))} de {o.get('ticker')} "
            f"({dollars(float(o.get('pourcentage', 0)) * valeur / 100)})")


def section_pistes(rapport: dict, valeur: float) -> None:
    """« Pistes testées » : ce que l'explorateur a essayé, avec les résultats du moteur. Sinon, le substitut."""
    agent = rapport.get("agent") or {}
    pistes = agent.get("pistes") or []
    explorateur = next((a for a in agent.get("agents") or [] if a.get("nom") == "explorateur"), None)
    if not pistes:
        section_substitut(rapport, valeur)
        return
    st.markdown("##### Pistes testées")
    if agent.get("intention"):
        st.markdown(f"*Finalité supposée de l'achat (hypothèse de l'agent) :* {agent['intention']}")
    if explorateur and explorateur.get("statut") == "repli" and explorateur.get("avis"):
        st.caption(explorateur["avis"])
    lignes = []
    for p in pistes:
        code = (p.get("verdict") or {}).get("code")
        couleur = COULEURS_VERDICT.get(code, MARINE)
        jambes = " ; ".join(jambe_txt(o, valeur) for o in p.get("ordres") or [])
        ligne = (f"- **{p.get('libelle_famille', '')}** : {jambes} → <b style=\"color:{couleur}\">"
                 f"{(p.get('verdict') or {}).get('libelle', '').lower()}</b> (score {note_txt(p.get('score'))})")
        if p.get("raison"):
            ligne += f"<br><span style=\"color:#6E6E71\">{p['raison']}</span>"
        lignes.append(ligne)
    st.markdown("\n".join(lignes), unsafe_allow_html=True)
    st.caption("Des possibilités testées par le moteur, pas des recommandations.")


CORRECTION_TEXTE = "L'agent a corrigé son texte après vérification."


def section_agent(rapport: dict) -> None:
    agent = rapport.get("agent") or {}
    if agent.get("erreur") or not agent.get("explication"):
        st.info(AVIS_SANS_AGENT + ".")
        if agent.get("erreur"):
            st.caption(f"Raison : {agent['erreur']}.")
        return
    # Les titres éventuels du texte de l'agent deviennent du gras, pour rester sous le titre de la partie.
    st.markdown(re.sub(r"(?m)^#{1,6}\s+(.+?)\s*$", r"\n**\1**\n", agent["explication"]))
    details = []
    if agent.get("modele"):
        details.append(f"Modèle : {agent['modele']}")
    if agent.get("duree_s") is not None:
        details.append(f"durée : {nombre(agent['duree_s'])} s")
    st.caption("Texte rédigé par l'agent à partir des résultats des outils. Aucun chiffre ne vient du "
               "modèle de langage. " + " ; ".join(details))
    if (agent.get("correction") or {}).get("faite"):
        st.caption(CORRECTION_TEXTE)
    afficher_verification(agent)


VERIFICATION_TEXTE = {
    "appuyee": "Vérifié : chaque chiffre vient des calculs, et le garde-fou confirme que le texte s'appuie sur eux.",
    "non_appuyee": "À lire avec prudence : une partie du texte ne correspond pas aux calculs. Fiez-vous aux chiffres du rapport.",
}


def afficher_verification(agent: dict) -> None:
    """Contrôle de l'explication (chiffres et ancrage contextuel), en une phrase, détails en légende."""
    a = agent.get("ancrage") or {}
    statut = a.get("statut")
    if statut == "appuyee":
        st.success(VERIFICATION_TEXTE["appuyee"])
    elif statut == "non_appuyee":
        st.warning(VERIFICATION_TEXTE["non_appuyee"])
    elif a.get("message"):
        st.caption(a["message"])
    details = []
    if a.get("chiffres_non_sources"):
        details.append("chiffres absents des calculs : " + ", ".join(a["chiffres_non_sources"]))
    if (a.get("ancrage") or {}).get("score") is not None:
        details.append(f"ancrage du passage le moins appuyé {nombre(a['ancrage']['score'], 2)} "
                       f"(seuil {nombre(a['ancrage']['seuil'], 2)})")
    gf = agent.get("garde_fou") or {}
    if gf.get("actif"):
        details.append(f"garde-fou Bedrock, version {gf.get('version')}")
    elif gf.get("avis"):
        details.append(gf["avis"])
    if details:
        st.caption("Contrôle : " + " ; ".join(details) + ".")


def section_etapes(rapport: dict, niveau: str) -> None:
    agent = rapport.get("agent") or {}
    if agent.get("trace") and not agent.get("erreur"):
        trace = agent["trace"]
        st.caption("Les outils appelés par l'agent, dans l'ordre.")
    else:
        trace = rapport["trace_moteur"]
        st.caption("Les appels au moteur de calcul faits par l'interface, dans l'ordre.")
    for i, t in enumerate(trace, start=1):
        args = ", ".join(f"{k}={v!r}" for k, v in (t.get("arguments") or {}).items())
        qui = f"{nom_agent(t['agent'])} · " if t.get("agent") else ""
        st.markdown(f"{t.get('etape', i)}. {qui}**`{t.get('outil', '?')}`**({args}) — {t.get('resultat_resume', '')}")
        if niveau == "detaille" and t.get("resultat") is not None:
            st.json(t["resultat"], expanded=False)


def phrases_fiche(fiche_client: dict) -> list[str]:
    """Phrases simples des règles de la fiche qui changent l'analyse (profil retenu, liquidités)."""
    d = fiche_client.get("deduit", {}) if isinstance(fiche_client, dict) else {}
    phrases = []
    if d.get("profil", {}).get("decide_par") == "capacite":
        phrases.append(d["profil"]["phrase"])
    if d.get("besoin_liquidite_pct", {}).get("valeur"):
        phrases.append(d["besoin_liquidite_pct"]["phrase"])
    return phrases


def section_sources(rapport: dict, persona: str) -> None:
    sources = {}
    for r in (rapport["fiche_client"], rapport["fiche_instrument"], rapport["simulation"], rapport["taille"] or {}):
        for s in r.get("sources", []) if isinstance(r, dict) else []:
            sources[s["id"]] = s
    publies = [s for s in sources.values() if s["nature"] == "publie"]
    hypotheses = [s for s in sources.values() if s["nature"] != "publie"]
    phrases = phrases_fiche(rapport["fiche_client"])
    if phrases:
        st.markdown("**Votre fiche**")
        for p in phrases:
            st.markdown(f"- {p}")
    st.markdown("**Faits publiés**")
    for s in publies:
        st.markdown(f"- {s['libelle']} — {s['source']} ({s['date']})")
    st.markdown("**Hypothèses du projet**")
    for s in hypotheses:
        st.markdown(f"- {s['libelle']} — {s['source']}")
    enregistre = client_enregistre(persona)
    origine_valeur = "montant fictif choisi par l'interface" if enregistre["exemple"] else "montant saisi à l'écran"
    st.markdown(f"- Valeur du portefeuille de {enregistre['nom']} : {dollars(valeur_pf(persona))}, "
                f"{origine_valeur}. {enregistre['description']}")
    st.markdown("- Le rapport suppose que l'ordre est exécuté, quel que soit son type.")
    origine = api.origine_references()
    if origine.get("message"):
        st.markdown("**Fichiers de référence**")
        st.markdown(f"- {origine['message']}")
    p = rapport["simulation"].get("periode", {})
    st.markdown("**Scénarios**")
    st.markdown(f"- Les notes de risque rejouent l'historique du {p.get('debut', '?')} au {p.get('fin', '?')}, "
                f"en {p.get('devise', 'CAD')}, comme si le portefeuille avait existé tel quel. "
                "C'est le passé, pas une prévision.")
    st.markdown("**Limites**")
    indet = [THEMES.get(k, k) for k, e in rapport["fiche_instrument"].get("etiquettes", {}).items()
             if e.get("valeur") == "indetermine"]
    if indet:
        st.markdown(f"- Thème(s) inconnu(s) pour {rapport['ordre']['ticker']} : {', '.join(indet)}.")
    for limite in (rapport["simulation"].get("operation") or {}).get("limites", []):
        st.markdown(f"- {limite}")
    st.markdown("- Cinq ans d'historique ne contiennent pas toutes les crises possibles.")
    st.markdown("- L'outil vérifie la compatibilité avec votre politique. Il ne juge pas la qualité du "
                "placement et ne remplace pas un conseiller.")


def afficher_rapport(persona: str, rapport: dict, fiche_actuelle: dict) -> None:
    sim = rapport["simulation"]
    valeur = valeur_pf(persona)
    st.divider()
    st.subheader(TITRE_RAPPORT)
    if rapport["fiche"] != fiche_actuelle:
        st.warning(f"Votre fiche a changé. Cliquez sur « {BOUTON_ACTION} » pour mettre le rapport à jour.")
    if "erreur" in sim:
        st.error(sim["erreur"])
        return
    fc = rapport["fiche_client"]
    niveau = fc.get("deduit", {}).get("niveau_detail", {}).get("valeur", "standard")
    exp = fc.get("questionnaire", {}).get("experience", "intermediaire")
    ouvert = exp == "avancee"

    bloc_verdict(sim, rapport, valeur)
    bloc_operation(sim)
    bloc_changements(rapport, st.session_state.get(f"precedent_{persona}"))
    section_possible(rapport["taille"], valeur)
    zone_substitut = st.container()  # remplie après la réponse de l'agent, qui choisit le substitut
    st.caption(rapport["ordre"].get("hypothese_execution", "Le rapport suppose que l'ordre est exécuté."))

    st.markdown("#### En détail")
    if not ouvert:
        st.caption(f"Détails repliés pour l'expérience « {libelle_option('experience', exp)} ». "
                   "Ouvrez une section pour la lire.")
    with st.expander("Règles strictes", expanded=ouvert or sim["verdict"]["code"] == "incompatible"):
        section_contraintes(sim)
    with st.expander("Les trois notes, avant → après", expanded=ouvert):
        section_notes(sim, niveau)
    if sim["verdict"]["code"] != "incompatible":
        with st.expander("Solidité du résultat", expanded=False):
            section_solidite(sim.get("solidite"))

    # L'explication s'affiche au-dessus des étapes, mais n'existe qu'une fois l'analyse finie.
    zone_explication, zone_etapes = st.container(), st.container()
    etapes_affichees = False
    if rapport.get("agent") is None:
        with zone_etapes:
            etapes_affichees = analyser_en_direct(rapport, niveau)
        if not etapes_affichees:  # agent sans annonce d'étapes : l'attente reste un simple indicateur
            with zone_etapes, st.spinner(ATTENTE_AGENT):
                o = rapport["ordre"]
                rapport["agent"] = appeler_agent(rapport["fiche"], o["ticker"], o["sens"], o["pourcentage"],
                                                 operation_moteur(o.get("operation")))
    with zone_substitut:
        section_pistes(rapport, valeur)
    with zone_explication, st.expander("Explication de l'agent", expanded=ouvert):
        section_agent(rapport)
    if not etapes_affichees:
        with zone_etapes, st.expander(TITRE_ETAPES, expanded=False):
            section_etapes(rapport, niveau)
    with st.expander("Sources, hypothèses et limites", expanded=False):
        section_sources(rapport, persona)
    st.caption("Vous décidez. Le rapport renseigne ; il ne bloque rien et ne conseille rien.")


# ---------------------------------------------------------------- analyse en direct

def nom_agent(code: str) -> str:
    return NOMS_AGENTS.get(code, f"Agent {code}")


def rendu_en_direct(etapes: list[dict]) -> str:
    """Liste des étapes, dans l'ordre : « … » pendant l'étape, « ✓ » et son résultat quand elle finit."""
    lignes = []
    for e in etapes:
        agent = f" :gray[· {nom_agent(e['agent'])}]" if e.get("agent") else ""
        if e["fini"]:
            resume = f"  \n  :gray[{e['resume']}]" if e.get("resume") else ""
            lignes.append(f"- ✓ {e['libelle']}{agent}{resume}")
        else:
            lignes.append(f"- … **{e['libelle']}**{agent}")
    return "\n".join(lignes) if lignes else "- … **Je commence l'analyse.**"


def analyser_en_direct(rapport: dict, niveau: str) -> bool:
    """Fait travailler l'agent en montrant chaque étape au moment où elle se passe.

    L'agent tourne dans un fil à part ; son crochet `sur_etape` ne fait que déposer les
    événements dans une file. Seul le fil du script touche à l'affichage. Renvoie False si
    l'agent ne sait pas annoncer ses étapes : l'appelant garde alors le simple indicateur d'attente.
    """
    try:
        from agent.inspection import inspecter
    except Exception:
        return False
    if not accepte_sur_etape(inspecter):
        return False

    file: queue.Queue = queue.Queue()
    sortie: dict = {}
    o = rapport["ordre"]

    def travail():
        sortie["r"] = appeler_agent(rapport["fiche"], o["ticker"], o["sens"], o["pourcentage"],
                                    operation_moteur(o.get("operation")), sur_etape=file.put)

    fil = threading.Thread(target=travail, name="analyse-agent", daemon=True)
    debut = time.monotonic()
    fil.start()
    etapes: list[dict] = []  # outils et phases, dans l'ordre où ils arrivent
    par_numero: dict = {}

    def clore_phases():
        for x in etapes:
            if x.get("phase") and not x["fini"]:
                x["fini"] = True

    with st.status(EN_DIRECT_AGENT, expanded=True) as statut:
        zone = st.empty()
        zone.markdown(rendu_en_direct(etapes))
        while fil.is_alive() or not file.empty():
            if time.monotonic() - debut > DELAI_MAX_AGENT_S:
                break
            try:
                ev = file.get(timeout=0.15)
            except queue.Empty:
                continue
            if not isinstance(ev, dict):
                continue
            moment = ev.get("moment")
            if moment == "debut_outil":
                # Une « rédaction » suivie d'un nouvel outil n'était qu'un choix de l'étape suivante.
                while etapes and etapes[-1].get("moment") == "redaction" and not etapes[-1]["fini"]:
                    etapes.pop()
                clore_phases()
                e = {"libelle": ev.get("libelle") or LIBELLES_OUTILS.get(ev.get("outil"), f"J'appelle {ev.get('outil')}."),
                     "agent": ev.get("agent"), "fini": False, "resume": ""}
                etapes.append(e)
                par_numero[ev.get("etape", len(etapes))] = e
            elif moment == "fin_outil":
                e = par_numero.get(ev.get("etape")) or next(
                    (x for x in reversed(etapes) if not x["fini"] and not x.get("phase")), None)
                if e is not None:
                    e["fini"], e["resume"] = True, str(ev.get("resultat_resume") or "")
            elif moment in LIBELLES_PHASES:
                if etapes and etapes[-1].get("moment") == moment and not etapes[-1]["fini"]:
                    continue
                clore_phases()
                etapes.append({"libelle": LIBELLES_PHASES[moment], "phase": True, "moment": moment,
                               "fini": False, "agent": ev.get("agent")})
            elif moment == "fin":
                clore_phases()
            else:
                continue
            zone.markdown(rendu_en_direct(etapes))
        r = sortie.get("r")
        if r is None:
            r = {"explication": None, "trace": [], "erreur": "l'agent a dépassé le temps prévu"}
        # Chaque étape de la trace garde le nom de l'agent qui l'a faite (annoncé en direct).
        outils_vus = [x for x in etapes if not x.get("phase")]
        for i, t in enumerate(r.get("trace") or []):
            if isinstance(t, dict) and not t.get("agent"):
                e = par_numero.get(t.get("etape")) or (outils_vus[i] if i < len(outils_vus) else None)
                if e and e.get("agent"):
                    t["agent"] = e["agent"]
        rapport["agent"] = r
        # La liste en direct se replie en « Étapes de l'analyse », avec le détail complet.
        zone.empty()
        section_etapes(rapport, niveau)
        duree = time.monotonic() - debut
        nb_outils = sum(1 for x in etapes if not x.get("phase"))
        statut.update(label=f"{TITRE_ETAPES} · {nb_outils} étape(s) en {nombre(duree, 0)} s",
                      state="complete", expanded=False)
    return True


# ---------------------------------------------------------------- rendu : ordre

def phrase_execution(type_ordre: str, prix: float | None) -> str:
    if type_ordre == "marche" or prix is None:
        return "Le rapport suppose que l'ordre est exécuté au prix du moment."
    return f"Le rapport suppose que l'ordre est exécuté à {dollars(prix, 2)}."


def onglet_ordre(persona: str, fiche: dict) -> None:
    univers = instruments()
    prix = derniers_prix_cad()
    valeur = valeur_pf(persona)
    pf = st.session_state[f"pf_{persona}"]

    c1, c2 = st.columns([2, 1.4])
    c1.selectbox("Titre", list(univers), key=f"o_{persona}_ticker",
                 format_func=lambda t: f"{t} — {univers[t]['nom']}")
    c2.radio("Opération", list(OPERATIONS), key=f"o_{persona}_operation", horizontal=True,
             format_func=lambda k: OPERATIONS[k]["libelle"])
    ticker = st.session_state[f"o_{persona}_ticker"]
    operation = st.session_state[f"o_{persona}_operation"]
    sens = OPERATIONS[operation]["sens"]

    c3, c4, c5 = st.columns([1.4, 1.2, 1.2])
    c3.number_input("Montant ($ CA)", min_value=100.0, max_value=float(valeur), step=500.0,
                    key=f"o_{persona}_montant", format="%.0f")
    montant = float(st.session_state[f"o_{persona}_montant"])
    pourcentage = round(montant / valeur * 100, 4)
    c3.markdown(f"= **{pct(pourcentage)}** de votre portefeuille ({dollars(valeur)})")
    c4.selectbox("Type d'ordre", list(TYPES_ORDRE), key=f"o_{persona}_type",
                 format_func=lambda k: TYPES_ORDRE[k]["libelle"])
    type_ordre = st.session_state[f"o_{persona}_type"]
    prix_ordre = None
    dernier = prix.get(ticker)
    if TYPES_ORDRE[type_ordre]["prix"]:
        cle_prix = f"o_{persona}_prix_{ticker}_{type_ordre}"
        st.session_state.setdefault(cle_prix, round(dernier, 2) if dernier else 1.0)
        c5.number_input(TYPES_ORDRE[type_ordre]["prix"], min_value=0.01, step=1.0, key=cle_prix, format="%.2f")
        prix_ordre = float(st.session_state[cle_prix])
    elif dernier:
        c5.markdown(f"Dernier prix connu  \n**{dollars(dernier, 2)}**")
    c4.caption(TYPES_ORDRE[type_ordre]["aide"])

    detenu = pf.get(ticker, 0.0) * valeur / 100
    deja = f"Vous détenez {dollars(detenu)} de {ticker}." if detenu > 0 else f"Vous ne détenez pas de {ticker}."
    if OPERATIONS[operation].get("aide"):
        st.caption(OPERATIONS[operation]["aide"] + f" {deja}")
    elif sens == "achat":
        st.caption(f"Un achat est payé avec vos liquidités : {dollars(pf.get('ZST.TO', 0.0) * valeur / 100)} "
                   f"disponibles. {deja}")
    else:
        st.caption(f"Une vente est versée dans vos liquidités. {deja}")

    b1, b2, _ = st.columns([1, 1.4, 2])
    inspecter = b1.button(BOUTON_ACTION, type="primary", key="inspecter", width="stretch")
    passer = b2.button("Passer l'ordre (simulé)", key="passer", width="stretch")

    details = {"operation": operation, "montant": montant, "type": type_ordre, "prix": prix_ordre,
               "hypothese_execution": phrase_execution(type_ordre, prix_ordre)}
    if inspecter:
        ancien = st.session_state.get(f"rapport_{persona}")
        if ancien is not None:
            st.session_state[f"precedent_{persona}"] = ancien
        st.session_state[f"rapport_{persona}"] = inspecter_moteur(persona, fiche, ticker, sens, pourcentage, details)
        st.session_state.pop(f"message_{persona}", None)

    if passer and operation_moteur(operation) != "comptant":
        st.session_state[f"message_{persona}"] = (
            "info", f"{OPERATIONS[operation]['nom']} : analysée seulement, non ajoutée au portefeuille de la session.")
    elif passer:
        r = api.simuler_ordre(fiche, ticker, sens, pourcentage)
        if "erreur" in r:
            st.session_state[f"message_{persona}"] = ("erreur", r["erreur"])
        else:
            st.session_state[f"pf_{persona}"] = {t: float(w) for t, w in r["portefeuille_apres_pct"].items()}
            st.session_state[f"ordres_{persona}"] = st.session_state.get(f"ordres_{persona}", []) + [{
                "Opération": OPERATIONS[operation]["nom"], "Titre": ticker, "Montant ($ CA)": round(montant),
                "Part (%)": round(pourcentage, 1), "Type": TYPES_ORDRE[type_ordre]["libelle"],
                "Prix ($ CA)": round(prix_ordre, 2) if prix_ordre else None,
                "Verdict": r["verdict"]["libelle"]}]
            st.session_state[f"message_{persona}"] = (
                "ok", f"{OPERATIONS[operation]['nom']} de {dollars(montant)} de {ticker} "
                      f"({TYPES_ORDRE[type_ordre]['libelle'].lower()}) ajouté au portefeuille de cette session. "
                      f"Verdict : {r['verdict']['libelle'].lower()}. Aucune transaction réelle n'a eu lieu.")
            st.rerun()

    message = st.session_state.get(f"message_{persona}")
    if message:
        {"ok": st.success, "info": st.info}.get(message[0], st.error)(message[1])

    rapport = st.session_state.get(f"rapport_{persona}")
    if rapport is not None:
        afficher_rapport(persona, rapport, fiche)
    else:
        st.markdown(f"Cliquez sur **{BOUTON_ACTION}** pour savoir si cet ordre respecte votre politique, "
                    "avant de le passer.")
    essai_garde_fou(persona)


def soumettre_au_garde_fou(texte: str) -> dict:
    """Le texte va au seul garde-fou Bedrock ; aucun modèle n'y répond. Renvoie toujours {statut, message}."""
    try:
        from agent.garde_fou import essayer_garde_fou  # import paresseux : le module peut être absent
        r = essayer_garde_fou(texte)
    except Exception as exc:  # l'essai ne doit jamais faire tomber la page
        return {"statut": "indisponible", "message": f"Essai impossible ({type(exc).__name__})."}
    return r if isinstance(r, dict) else {"statut": "indisponible", "message": "Réponse illisible."}


def essai_garde_fou(persona: str) -> None:
    """Essai du garde-fou, à part du rapport : on voit ce qu'il refuse, sans conversation avec l'agent."""
    with st.expander("Essai du garde-fou"):
        st.caption("Le garde-fou filtre les échanges avec le modèle. Il refuse le conseil personnalisé "
                   "et les transactions réelles.")
        with st.form(key=f"form_essai_{persona}"):
            texte = st.text_input("Votre demande", key=f"essai_{persona}",
                                  placeholder="Par exemple : passe cet ordre pour de vrai sur mon compte")
            envoyee = st.form_submit_button("Soumettre au garde-fou", key=f"soumettre_{persona}")
        if envoyee:
            with st.spinner("Le garde-fou examine la demande…"):
                st.session_state[f"essai_resultat_{persona}"] = soumettre_au_garde_fou(texte)
        r = st.session_state.get(f"essai_resultat_{persona}")
        if not r:
            return
        if r.get("statut") == "refuse":
            st.error(r.get("message", ""))
        elif r.get("statut") == "accepte":
            st.success(r.get("message", ""))
        else:
            st.info(r.get("message", ""))
        st.caption("Aucune réponse n'est produite : l'outil n'est pas un agent conversationnel.")


# ---------------------------------------------------------------- page

STYLE = f"""<style>
.bandeau-simulation {{background:{MARINE};color:#FFFFFF;border-left:5px solid {ROUGE_THEME};
  padding:0.55rem 1rem;border-radius:4px;font-size:0.92rem;margin-bottom:0.6rem;}}
div[data-testid="stExpander"] summary p {{font-weight:600;color:{MARINE};}}
h1, h2, h3, h4 {{color:{MARINE};}}
</style>"""


def main() -> None:
    st.set_page_config(page_title="Garder le cap", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(f'<div class="bandeau-simulation">{BANDEAU}</div>', unsafe_allow_html=True)

    # Streamlit oublie l'état d'un widget non affiché : on garde celui des autres clients.
    for cle in list(st.session_state.keys()):
        if isinstance(cle, str) and cle.startswith(("q_", "o_")):
            st.session_state[cle] = st.session_state[cle]

    with st.sidebar:
        st.title("Garder le cap")
        st.caption(SOUS_TITRE)
        tous = clients()
        persona = st.radio("Client", list(tous), key="persona",
                           format_func=lambda c: tous[c]["nom"] + (" (exemple)" if tous[c]["exemple"] else ""))
    initialiser(persona)
    fiche = fiche_session(persona)
    fiche_client = api.lire_fiche_client(fiche)

    with st.sidebar:
        if "erreur" not in fiche_client:
            d = fiche_client["deduit"]
            st.markdown(f"Profil **{d['profil']['libelle']}**  \nHorizon "
                        f"{nombre(d['horizon_annees']['valeur'], 0)} ans  \n"
                        f"Portefeuille {dollars(valeur_pf(persona))}")
        ecarts = fiche_modifiee(persona, fiche)
        if ecarts:
            st.markdown("Fiche modifiée : " + " ; ".join(ecarts))
        st.button("Revenir à la fiche d'origine", on_click=reinitialiser, args=(persona,),
                  key=f"reinit_{persona}")
        st.divider()
        st.markdown("**Les trois verdicts**")
        for code, lib, sens in (("compatible", "Compatible", "respecte votre politique."),
                                ("en_tension", "En tension", "sort d'une limite de votre politique."),
                                ("incompatible", "Incompatible", "touche une règle stricte.")):
            st.markdown(f'<span style="color:{COULEURS_VERDICT[code]};font-weight:700;">{lib}</span> : '
                        f"l'ordre {sens}", unsafe_allow_html=True)
        st.caption(MISSION)

    st.title(client_enregistre(persona)["nom"])
    st.caption(client_enregistre(persona)["description"])
    onglets = st.tabs(["Fiche", "Portefeuille", "Ordre"])
    with onglets[0]:
        onglet_fiche(persona, fiche_client)
    with onglets[1]:
        onglet_portefeuille(persona, fiche, fiche_client)
    with onglets[2]:
        onglet_ordre(persona, fiche)


main()
