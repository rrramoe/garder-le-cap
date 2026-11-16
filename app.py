"""Garder le cap : interface (Streamlit), prototype de service de gestion des risques.

Lancement : streamlit run app.py --server.address localhost

Le code calcule, le modèle explique : tous les chiffres affichés viennent de moteur.api. L'agent
(agent/inspection.py), s'il est présent, n'ajoute que l'explication et la trace de ses appels.

Ce fichier ne fait que monter la page : l'en-tête, puis la page choisie. Le reste vit dans `interface/` :
`theme` (couleurs et feuille de style), `composants` (HTML et SVG), `textes` (mots et formats),
`etat` (session, moteur, agents) et une page par destination.
"""

from __future__ import annotations

import streamlit as st

from moteur import api
from interface import composants as C
from interface import etat, page_aide, page_negocier, page_portefeuille, page_profil
from interface.textes import BANDEAU, PAGES
from interface.theme import CSS


def entete() -> str:
    """Le bandeau de simulation, toujours visible, puis la barre : la marque, les destinations, le compte."""
    tous = etat.clients()
    with st.container(key="entete"):
        C.montrer(C.bandeau(BANDEAU))
        with st.container(key="barre"):
            gauche, milieu, droite = st.columns([2.6, 5, 2.6], vertical_alignment="center")
            with gauche:
                C.montrer(C.entete_marque())
            milieu.radio("Navigation", list(PAGES), key="page", horizontal=True, label_visibility="collapsed",
                         format_func=PAGES.get)
            with droite.container(key="compte"):
                with st.popover(tous[st.session_state["persona"]]["nom"], icon=":material/account_circle:"):
                    st.radio("Compte", list(tous), key="persona",
                             format_func=lambda c: f"**{tous[c]['nom']}** · {tous[c]['description']}")
    return st.session_state["persona"]


def main() -> None:
    st.set_page_config(page_title="Garder le cap", page_icon="🧭", layout="wide",
                       initial_sidebar_state="collapsed")
    C.montrer(CSS)
    etat.garder_les_choix()
    persona = entete()
    etat.initialiser(persona)
    fiche = etat.fiche_session(persona)
    fiche_client = api.lire_fiche_client(fiche)

    page = st.session_state["page"]
    if page == "negocier":
        page_negocier.afficher(persona, fiche)
    elif page == "profil":
        page_profil.afficher(persona, fiche, fiche_client)
    elif page == "aide":
        page_aide.afficher(persona)
    else:
        page_portefeuille.afficher(persona, fiche, fiche_client)


main()
