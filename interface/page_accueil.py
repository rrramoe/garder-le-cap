"""L'ouverture du service : l'introduction en quelques panneaux, puis le choix d'un compte."""

from __future__ import annotations

import streamlit as st

from moteur import api
from interface import composants as C
from interface import etat
from interface.textes import (AIDE_ANGLES, BOUTON_ESSAI, BOUTON_PASSER_INTRO, INTRODUCTION, LIBELLES_OUTILS, LIMITE,
                              NOMS_AGENTS, VERDICTS_AIDE, angles_du_bloc, dollars, nom_angle, pct, raison_courte)


# ---------------------------------------------------------------- les vues de l'introduction

def _exemple() -> tuple[dict, dict] | None:
    """Le premier compte enregistré qui a un ordre prêt, et sa fiche pour le moteur : les vues sont de vraies vues."""
    for cid, c in etat.clients().items():
        if c.get("ordre_demo"):
            depart = etat.client_de_depart(cid)
            return depart, {"id": cid, "nom": depart["nom"], "questionnaire": depart["questionnaire"],
                            "portefeuille_pct": depart["portefeuille_pct"]}
    return None


@st.cache_data(show_spinner=False)
def _simulation(fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    return api.simuler_ordre(fiche, ticker, sens, pourcentage)


@st.cache_data(show_spinner=False)
def _fiche_client(fiche: dict) -> dict:
    return api.lire_fiche_client(fiche)


def _vue_verdict() -> str:
    exemple = _exemple()
    if not exemple:
        return ""
    client, fiche = exemple
    o = client["ordre_demo"]
    sim = _simulation(fiche, o["ticker"], o["sens"], float(o["pourcentage"]))
    if "erreur" in sim:
        return ""
    ordre = (f"{client['nom']} · {str(o['sens']).capitalize()} de {dollars(o['pourcentage'] * client['valeur'] / 100)} "
             f"de {o['ticker']} · {pct(o['pourcentage'])} du portefeuille")
    return C.carte_verdict(ordre, sim["verdict"]["libelle"], sim["verdict"]["code"], raison_courte(sim))


def _vue_politique() -> str:
    from interface.page_profil import articles_de_la_politique
    exemple = _exemple()
    if not exemple:
        return ""
    client, fiche = exemple
    fc = _fiche_client(fiche)
    if "erreur" in fc:
        return ""
    articles, _, _ = articles_de_la_politique(fc)
    choisis = [a for a in articles if 'class="glc-article"' in a][2:5]  # profil, limites de risque, répartition
    return C.document("Politique de placement", f"Établie pour {client['nom']} à partir de sa fiche", choisis)


def _vue_angles() -> str:
    exemple = _exemple()
    if not exemple:
        return ""
    client, fiche = exemple
    o = client["ordre_demo"]
    sim = _simulation(fiche, o["ticker"], o["sens"], float(o["pourcentage"]))
    if "erreur" in sim:
        return ""
    apres = sim["apres"]
    lignes = []
    for angle in angles_du_bloc(apres):
        n = apres["notes"][angle]
        sans = n.get("sans_objet") or n.get("note") is None
        lignes.append({"nom": nom_angle(angle), "note": None if sans else n["note"],
                       "decide": angle == apres.get("dimension_min") and not sans and
                       sim["verdict"]["code"] != "incompatible", "aide": AIDE_ANGLES.get(angle, "")})
    pastilles = " ".join(C.pastille(lib, code) for code, lib, _ in VERDICTS_AIDE)
    return (f'<div class="glc-carte">{C.angles(lignes, LIMITE, f"Le trait marque la note de passage ({LIMITE:g}).")}'
            f'<p style="margin:14px 0 0 0">{pastilles}</p></div>')


def _vue_agents() -> str:
    principal, explorateur = NOMS_AGENTS.get("principal", ""), NOMS_AGENTS.get("explorateur", "")
    lignes = [{"libelle": LIBELLES_OUTILS["lire_fiche_client"], "agent": principal, "fini": True},
              {"libelle": LIBELLES_OUTILS["simuler_ordre"], "agent": "", "fini": True},
              {"libelle": LIBELLES_OUTILS["envoyer_explorateur"], "agent": "", "fini": True},
              {"libelle": LIBELLES_OUTILS["simuler_scenario"], "agent": explorateur, "fini": True},
              {"libelle": LIBELLES_OUTILS["juger_pistes"], "agent": principal, "fini": True},
              {"libelle": "Je rédige l'explication.", "agent": "", "fini": False}]
    return C.en_direct("Analyse en cours", lignes)


def _vue_limites() -> str:
    return ('<div class="glc-carte">' + C.definitions([
        ("Simulation", "Aucune transaction réelle n'a lieu."),
        ("Information", "Le service renseigne. Il ne conseille pas et ne décide pas à votre place."),
        ("Garde-fou", "Il refuse le conseil personnalisé et les demandes de transaction réelle."),
        ("Passé", "Les notes de risque rejouent cinq ans d'historique. Ce n'est pas une prévision."),
    ]) + "</div>")


VUES = {"verdict": _vue_verdict, "politique": _vue_politique, "angles": _vue_angles, "agents": _vue_agents,
        "limites": _vue_limites}


# ---------------------------------------------------------------- l'introduction

def introduction() -> None:
    """Quelques panneaux qui défilent : une vraie vue du service et deux lignes. On peut la passer d'un clic."""
    dernier = len(INTRODUCTION) - 1
    n = max(0, min(dernier, st.session_state.get("intro_n", 0)))
    cle, titre, lignes = INTRODUCTION[n]
    with st.container(key="introduction"):
        haut_gauche, haut_droite = st.columns([3, 1], vertical_alignment="center")
        with haut_gauche:
            points = "".join(f'<i class="{"ici" if i == n else ""}"></i>' for i in range(dernier + 1))
            C.montrer(f'<div class="glc-pas-intro"><span>{n + 1} / {dernier + 1}</span>{points}</div>')
        haut_droite.button(BOUTON_PASSER_INTRO, key="passer_intro", type="tertiary", on_click=etat.finir_introduction)
        gauche, droite = st.columns([1, 1.25], gap="large", vertical_alignment="top")
        with gauche:
            C.montrer(f'<div class="glc-intro"><h1>{C.e(titre)}</h1>'
                      + "".join(f"<p>{C.e(l)}</p>" for l in lignes) + "</div>")
            retour, suivant = st.columns([1, 1.6])
            if n > 0:
                retour.button("Retour", key="intro_retour", width="stretch",
                              on_click=etat.avancer_introduction, args=(-1, dernier))
            suite = "Suivant" if n < dernier else ("Reprendre" if st.session_state.get("compte_choisi")
                                                   else "Choisir un compte")
            suivant.button(suite, key="intro_suivant", type="primary", width="stretch",
                           on_click=etat.avancer_introduction, args=(1, dernier))
        with droite:
            C.montrer(f'<div class="glc-vue">{VUES[cle]()}</div>')


# ---------------------------------------------------------------- le choix d'un compte

def comptes() -> None:
    """Les comptes déjà prêts, en cartes, et le nouveau compte. Un clic ouvre le compte sur son profil."""
    tous = etat.clients()
    prets = {cid: c for cid, c in tous.items() if c["exemple"]}
    nouveaux = {cid: c for cid, c in tous.items() if not c["exemple"]}
    C.montrer(C.titre_page("Choisissez un compte",
                           "Pour commencer, prenez un compte déjà prêt : sa fiche et son portefeuille sont remplis."))
    colonnes = st.columns(max(len(prets), 1), gap="medium")
    for colonne, (cid, c) in zip(colonnes, prets.items()):
        with colonne, st.container(key=f"carte_compte_{cid}"):
            fc = _fiche_client({"id": cid, "nom": c["nom"], "questionnaire": c["questionnaire"],
                                "portefeuille_pct": c["portefeuille_pct"]})
            profil = fc["deduit"]["profil"]["libelle"] if "erreur" not in fc else ""
            faits = (f'<div><span>Profil</span><b>{C.e(profil)}</b></div>' if profil else "") + \
                    f'<div><span>Portefeuille</span><b>{C.e(dollars(c["valeur"]))}</b></div>'
            C.montrer(f'<p class="glc-h2">{C.e(c["nom"])}{C.marqueur("compte prêt")}</p>'
                      f'<p class="glc-sur">{C.e(c["description"])}</p>'
                      f'<div class="glc-faits">{faits}</div>')
            st.button("Ouvrir ce compte", key=f"compte_{cid}", width="stretch",
                      on_click=etat.choisir_compte, args=(cid,))
    for cid, c in nouveaux.items():
        with st.container(key=f"carte_compte_{cid}"):
            gauche, droite = st.columns([3, 1], vertical_alignment="center")
            with gauche:
                C.montrer(f'<p class="glc-h2">{C.e(c["nom"])}</p>'
                          '<p class="glc-sur">Partez d\'une fiche vide : répondez aux questions, '
                          "puis composez votre portefeuille.</p>")
            droite.button("Créer un compte", key=f"compte_{cid}", width="stretch",
                          on_click=etat.choisir_compte, args=(cid,))
    bas_gauche, bas_droite = st.columns([1, 1], vertical_alignment="center")
    bas_gauche.button(BOUTON_ESSAI, key="essayer", type="tertiary", on_click=etat.essayer_avec_un_exemple)
