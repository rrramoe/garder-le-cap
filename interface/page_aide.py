"""Page « Aide » : comprendre l'analyse, et poser une question pour voir ce que le service refuse."""

from __future__ import annotations

import streamlit as st

from interface import composants as C
from interface import etat
from interface.textes import (AIDE_ANGLES, ANGLES_DEFAUT, FONCTIONNEMENT, LIMITE, MISSION, SERVICES_AWS, TRACE_AIDE,
                              VERDICTS_AIDE, nom_angle)


def question(persona: str) -> None:
    """La question va au seul garde-fou : on voit ce qu'il refuse, sans conversation avec un agent."""
    with st.container(key="carte_question"):
        C.montrer(C.h2("Posez une question",
                       "Le service refuse le conseil personnalisé et les transactions réelles. Essayez."))
        with st.form(key=f"form_essai_{persona}", border=False):
            gauche, droite = st.columns([4, 1], vertical_alignment="bottom")
            texte = gauche.text_input("Votre question", key=f"essai_{persona}",
                                      placeholder="Par exemple : passe cet ordre pour de vrai sur mon compte")
            envoyee = droite.form_submit_button("Envoyer", key=f"soumettre_{persona}", width="stretch")
        if envoyee:
            with st.spinner("Le garde-fou examine la question…"):
                st.session_state[f"essai_resultat_{persona}"] = etat.soumettre_au_garde_fou(texte)
        r = st.session_state.get(f"essai_resultat_{persona}")
        if not r:
            return
        code = {"refuse": "incompatible", "accepte": "compatible"}.get(r.get("statut"))
        C.montrer(C.reponse(r.get("message", ""), code))
        st.caption("Aucune réponse n'est produite : le service n'est pas un agent conversationnel.")


def comprendre() -> None:
    verdicts = C.definitions([(C.pastille(lib, code), texte) for code, lib, texte in VERDICTS_AIDE])
    angles = C.definitions([(C.e(nom_angle(a)), AIDE_ANGLES.get(a, "")) for a in ANGLES_DEFAUT])
    gauche, droite = st.columns(2, gap="large")
    with gauche, st.container(key="carte_verdicts"):
        C.montrer(C.h2("Les trois verdicts") + verdicts)
    with droite, st.container(key="carte_aide_angles"):
        C.montrer(C.h2("Les angles", f"Chaque angle reçoit une note de 0 à 100. La note de passage est {LIMITE:g}. "
                                     "L'angle déterminant, le plus bas, décide du verdict.") + angles)


def fonctionnement() -> None:
    gauche, droite = st.columns(2, gap="large")
    with gauche, st.container(key="carte_fonctionnement"):
        C.montrer(C.h2("Comment ça marche") + C.pas(FONCTIONNEMENT)
                  + f'<p class="glc-legende">{C.e(TRACE_AIDE)}</p>')
    with droite, st.container(key="carte_services"):
        C.montrer(C.h2("Les services AWS", "Le rôle de chacun, en une ligne.")
                  + C.definitions([(C.e(nom), role) for nom, role in SERVICES_AWS]))


def afficher(persona: str) -> None:
    C.montrer(C.titre_page("Aide", MISSION))
    fonctionnement()
    comprendre()
    question(persona)
    _, droite = st.columns([2.2, 1])
    droite.button("Revoir l'introduction", key="revoir_intro", width="stretch", on_click=etat.revoir_introduction)
