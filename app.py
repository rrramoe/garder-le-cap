"""Garder le cap : interface (Streamlit), prototype de service de gestion des risques.

Lancement : streamlit run app.py --server.address localhost

Le code calcule, le modèle explique : tous les chiffres affichés viennent de moteur.api. L'agent
(agent/inspection.py), s'il est présent, n'ajoute que l'explication et la trace de ses appels.

Ce fichier ne fait que monter la page : l'en-tête, puis la page choisie. Le reste vit dans `interface/` :
`theme` (couleurs et feuille de style), `composants` (HTML et SVG), `textes` (mots et formats),
`etat` (session, moteur, agents), l'accueil (introduction, choix du compte) et une page par destination.
"""

from __future__ import annotations

import streamlit as st

from moteur import api
from interface import composants as C
from interface import etat, page_accueil, page_aide, page_negocier, page_portefeuille, page_profil
from interface.textes import BANDEAU, PAGES
from interface.theme import CSS


def entete(service: bool) -> str:
    """Le bandeau de simulation, toujours visible, puis la barre : la marque, les destinations, le compte.

    Avant le choix d'un compte (introduction, choix du compte), la barre ne porte que la marque."""
    tous = etat.clients()
    with st.container(key="entete"):
        C.montrer(C.bandeau(BANDEAU))
        with st.container(key="barre"):
            gauche, milieu, droite = st.columns([2.6, 5, 2.6], vertical_alignment="center")
            with gauche:
                C.montrer(C.entete_marque())
            if not service:
                return st.session_state["persona"]
            milieu.radio("Navigation", list(PAGES), key="page", horizontal=True, label_visibility="collapsed",
                         format_func=PAGES.get)
            # Le menu se referme quand un client est choisi : son conteneur change alors de clé.
            with droite.container(key=f"compte_{st.session_state.get('menu_compte', 0)}"):
                with st.popover(tous[st.session_state["persona"]]["nom"], icon=":material/account_circle:"):
                    st.radio("Compte", list(tous), key="persona", on_change=etat.fermer_le_menu,
                             format_func=lambda c: f"**{tous[c]['nom']}** · {tous[c]['description']}")
    return st.session_state["persona"]


def main() -> None:
    st.set_page_config(page_title="Garder le cap", page_icon="🧭", layout="wide",
                       initial_sidebar_state="collapsed")
    C.montrer(CSS)
    etat.garder_les_choix()
    etape = st.session_state["etape"]
    persona = entete(service=etape == "service")
    if etape == "introduction":
        page_accueil.introduction()
        return
    if etape == "comptes":
        page_accueil.comptes()
        return

    etat.initialiser(persona)
    fiche = etat.fiche_session(persona)
    complete = etat.fiche_complete(fiche)
    fiche_client = api.lire_fiche_client(fiche) if complete else None

    page = st.session_state["page"]
    if page == "aide":
        page_aide.afficher(persona)
    elif page == "profil":
        page_profil.afficher(persona, fiche, fiche_client)
    elif not complete:
        page_profil.fiche_a_completer(page)  # le portefeuille et l'ordre s'ouvrent quand la fiche est complète
    elif page == "negocier":
        page_negocier.afficher(persona, fiche)
    else:
        page_portefeuille.afficher(persona, fiche, fiche_client)


main()
