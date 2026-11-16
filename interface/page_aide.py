"""Page « Aide » : comment le service fonctionne, ses verdicts, ses angles, le rôle de chaque service AWS."""

from __future__ import annotations

import streamlit as st

from interface import composants as C
from interface import etat
from interface.textes import (AIDE_ANGLES, ANGLES_DEFAUT, FONCTIONNEMENT, LIMITE, MISSION, SERVICES_AWS, TRACE_AIDE,
                              VERDICTS_AIDE, nom_angle)


def afficher(persona: str) -> None:
    """Deux colonnes de blocs serrés, sans vide entre eux : comment ça marche et les verdicts d'un côté,
    les angles et les services de l'autre. La page se ferme là, sur le moyen de revoir l'introduction."""
    C.montrer(C.titre_page("Aide", MISSION))
    verdicts = C.definitions([(C.pastille(lib, code), texte) for code, lib, texte in VERDICTS_AIDE])
    angles = C.definitions([(C.e(nom_angle(a)), AIDE_ANGLES.get(a, "")) for a in ANGLES_DEFAUT])
    gauche, droite = st.columns(2, gap="medium")
    with gauche:
        with st.container(key="carte_fonctionnement"):
            C.montrer(C.h2("Comment ça marche") + C.pas(FONCTIONNEMENT)
                      + f'<p class="glc-legende">{C.e(TRACE_AIDE)}</p>')
        with st.container(key="carte_verdicts"):
            C.montrer(C.h2("Les trois verdicts") + verdicts)
    with droite:
        with st.container(key="carte_aide_angles"):
            C.montrer(C.h2("Les angles", f"Chaque angle reçoit une note de 0 à 100. La note de passage est {LIMITE:g}. "
                                         "L'angle déterminant, le plus bas, décide du verdict.") + angles)
        with st.container(key="carte_services"):
            C.montrer(C.h2("Les services AWS", "Le rôle de chacun, en une ligne.")
                      + C.definitions([(C.e(nom), role) for nom, role in SERVICES_AWS]))
    _, droite = st.columns([2.2, 1])
    droite.button("Revoir l'introduction", key="revoir_intro", width="stretch", on_click=etat.revoir_introduction)
