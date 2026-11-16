"""État de la session et appels au moteur et aux agents. Aucun affichage ici.

Le code calcule, le modèle explique : tous les chiffres viennent de moteur.api. L'agent
(agent/inspection.py), s'il est présent, n'ajoute que l'explication, les pistes et la trace de ses appels.
"""

from __future__ import annotations

import copy
import inspect
import time

import streamlit as st

from moteur import api, references
from interface.textes import (CHAMPS_Q, EXEMPLES_ENREGISTRES, NOUVEAU, OPERATIONS, PAGES, PERSONAS, QUESTIONNAIRE,
                              REPONSES_PAR_DEFAUT, THEMES, VALEUR_NOUVEAU, dollars, libelle_option,
                              libelle_theme_reponse)


def operation_moteur(cle: str | None) -> str:
    """Opération du moteur (comptant, marge, decouvert) pour une opération du formulaire."""
    return OPERATIONS.get(cle or "", {}).get("operation", "comptant")


def cle_q(persona: str, champ: str) -> str:
    return f"q_{persona}_{champ}"


# ---------------------------------------------------------------- clients

def nouveau_client() -> dict:
    """Un profil neutre et un portefeuille entièrement en liquidités, à composer à l'écran."""
    return {"id": NOUVEAU, "nom": "Nouveau client", "exemple": False, "valeur": VALEUR_NOUVEAU,
            "description": "profil et portefeuille à composer",
            "questionnaire": {**REPONSES_PAR_DEFAUT, "themes": {t: "neutre" for t in THEMES}},
            "portefeuille_pct": {references.encaisse(): 100.0}, "ordre_demo": None}


def client_de_depart(cid: str) -> dict:
    """Le client tel qu'enregistré au départ : un exemple de l'énoncé, ou le nouveau client vierge."""
    for ex in EXEMPLES_ENREGISTRES:
        if ex["id"] == cid:
            p = PERSONAS[cid]
            return {"id": cid, "nom": p["nom"], "exemple": True, "valeur": ex["valeur"],
                    "description": ex["description"], "questionnaire": copy.deepcopy(p["questionnaire"]),
                    "portefeuille_pct": dict(p["portefeuille_pct"]), "ordre_demo": p.get("ordre_demo")}
    return nouveau_client()


def clients() -> dict:
    """Les clients de la session : les exemples enregistrés, puis le nouveau client. Tous de la même forme."""
    if "clients" not in st.session_state:
        ids = [ex["id"] for ex in EXEMPLES_ENREGISTRES] + [NOUVEAU]
        st.session_state["clients"] = {cid: client_de_depart(cid) for cid in ids}
    return st.session_state["clients"]


def client_enregistre(cid: str) -> dict:
    return clients()[cid]


def valeur_pf(persona: str) -> float:
    return float(client_enregistre(persona)["valeur"])


def garder_les_choix() -> None:
    """Streamlit oublie l'état d'un champ non affiché : on garde les choix des autres pages et des autres clients."""
    s = st.session_state
    if "page" not in s:  # la page d'arrivée peut venir de l'adresse (?page=negocier)
        demandee = st.query_params.get("page", "")
        s["page"] = demandee if demandee in PAGES else next(iter(PAGES))
    s.setdefault("persona", next(iter(clients())))
    for cle in list(s.keys()):
        if not isinstance(cle, str):
            continue
        if cle in ("page", "persona") or cle.startswith(("q_", "o_")) or \
                (cle.startswith("nc_") and cle.endswith(("_valeur", "_titre", "_montant"))):
            s[cle] = s[cle]


def fermer_le_menu() -> None:
    st.session_state["menu_compte"] = st.session_state.get("menu_compte", 0) + 1


def essayer_avec_un_exemple() -> None:
    """Ouvre le billet d'ordre d'un client enregistré, déjà rempli : celui du compte s'il en a un, sinon le premier."""
    s = st.session_state
    tous = clients()
    if not tous[s["persona"]].get("ordre_demo"):
        s["persona"] = next((cid for cid, c in tous.items() if c.get("ordre_demo")), s["persona"])
    s["page"] = "negocier"
    s["accueil_vu"] = True


def initialiser(persona: str) -> None:
    p = client_enregistre(persona)
    q = p["questionnaire"]
    s = st.session_state
    for champ in CHAMPS_Q:
        s.setdefault(cle_q(persona, champ), q[champ])
    for theme in THEMES:
        s.setdefault(cle_q(persona, "theme_" + theme), q["themes"].get(theme, "neutre"))
    s.setdefault(f"pf_{persona}", {t: float(w) for t, w in p["portefeuille_pct"].items()})
    s.setdefault(f"ordres_{persona}", [])
    ordre = p.get("ordre_demo") or {}
    s.setdefault(f"o_{persona}_ticker", ordre.get("ticker", "XIU.TO"))
    s.setdefault(f"o_{persona}_operation", ordre.get("sens", "achat"))
    s.setdefault(f"o_{persona}_type", "marche")
    s.setdefault(f"o_{persona}_montant", round(float(ordre.get("pourcentage", 5)) * valeur_pf(persona) / 100, 2))


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
    """Libellés des réponses qui diffèrent du profil enregistré du client."""
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


# ---------------------------------------------------------------- portefeuille composé à l'écran

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


# ---------------------------------------------------------------- analyse

def analyser_par_le_moteur(persona: str, fiche: dict, ticker: str, sens: str, pourcentage: float,
                           details_ordre: dict | None = None) -> dict:
    """L'analyse structurée, appelée directement sur moteur.api, avec la trace des appels."""
    trace = []
    enregistre = client_enregistre(persona)
    client_affiche = persona if not fiche_modifiee(persona, fiche) and \
        fiche["portefeuille_pct"] == {t: float(w) for t, w in enregistre["portefeuille_pct"].items()} \
        else f"fiche de session ({enregistre['nom']})"

    def appel(outil, fonction, *args, **arguments):
        debut = time.perf_counter()
        r = fonction(*args)
        trace.append({"etape": len(trace) + 1, "outil": outil, "arguments": arguments, "resultat": r,
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
        "agent": None,  # rempli juste après l'affichage de l'analyse du moteur
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
    except Exception as exc:  # l'agent ne doit jamais faire tomber l'analyse
        return {"explication": None, "trace": [], "erreur": f"l'agent a échoué ({type(exc).__name__})"}
    if not isinstance(r, dict):
        return {"explication": None, "trace": [], "erreur": "réponse de l'agent illisible"}
    r.setdefault("trace", [])
    if not r.get("erreur") and not r.get("explication"):
        r["erreur"] = "aucune explication reçue"
    return r


def soumettre_au_garde_fou(texte: str) -> dict:
    """Le texte va au seul garde-fou Bedrock ; aucun modèle n'y répond. Renvoie toujours {statut, message}."""
    try:
        from agent.garde_fou import essayer_garde_fou  # import paresseux : le module peut être absent
        r = essayer_garde_fou(texte)
    except Exception as exc:  # l'essai ne doit jamais faire tomber la page
        return {"statut": "indisponible", "message": f"Essai impossible ({type(exc).__name__})."}
    return r if isinstance(r, dict) else {"statut": "indisponible", "message": "Réponse illisible."}
