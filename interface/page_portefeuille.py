"""Page « Portefeuille » : la valeur, la répartition, les positions, et où en est le portefeuille sur chaque angle."""

from __future__ import annotations

import streamlit as st

from moteur import api, references
from interface import composants as C
from interface import etat, marche
from interface.theme import BAISSE, BLEU_CLAIR, COULEUR_AUTRE, COULEURS_CLASSES, HAUSSE
from interface.textes import (AIDE_ANGLES, CLASSES, LIMITE, angles_du_bloc, dollars, instruments,
                              libelle_mesure, nom_angle, pct)


def composer(persona: str) -> None:
    """Composer le portefeuille à l'écran : la valeur totale, puis chaque position et son montant."""
    s = st.session_state
    cash = references.encaisse()
    univers = instruments()
    pf = s[f"pf_{persona}"]
    # Ouvert pour un client créé à l'écran ; replié pour un client enregistré, qui a déjà son portefeuille.
    ouvert = not etat.client_enregistre(persona)["exemple"] or set(pf) == {cash}
    with st.expander("Composer le portefeuille", expanded=ouvert):
        s.setdefault(f"nc_{persona}_valeur", float(etat.valeur_pf(persona)))
        c0, c1, c2, c3 = st.columns([1.5, 2.4, 1.3, 1], vertical_alignment="bottom")
        c0.number_input("Valeur totale ($ CA)", min_value=1_000.0, step=1_000.0, format="%.0f",
                        key=f"nc_{persona}_valeur", on_change=etat.changer_valeur, args=(persona,))
        c1.selectbox("Titre à ajouter", [t for t in univers if t != cash], key=f"nc_{persona}_titre",
                     format_func=lambda t: f"{t} — {univers[t]['nom']}")
        s.setdefault(f"nc_{persona}_montant", 10_000.0)
        c2.number_input("Montant ($ CA)", min_value=0.0, step=1_000.0, format="%.0f", key=f"nc_{persona}_montant")
        c3.button("Ajouter", key=f"nc_{persona}_ajouter", on_click=etat.ajouter_position, args=(persona,),
                  width="stretch")
        dispo = pf.get(cash, 0.0) * etat.valeur_pf(persona) / 100
        message = s.pop(f"nc_{persona}_message", None)
        if message:
            (st.success if message[0] == "ok" else st.error)(message[1])
        g, d = st.columns([3, 1.2], vertical_alignment="center")
        g.caption(f"Ce qui n'est pas placé reste en liquidités : {dollars(dispo)}, "
                  f"{pct(pf.get(cash, 0.0))} du portefeuille.")
        d.button("Tout remettre en liquidités", key=f"nc_{persona}_vider", on_click=etat.vider_portefeuille,
                 args=(persona,), width="stretch")


def _apercu(persona: str, fiche_client: dict) -> str:
    """La valeur et son allure sur un an dans un panneau sombre ; à côté, la répartition par classe d'actif,
    face aux zones de la politique de placement."""
    valeur = etat.valeur_pf(persona)
    pf = fiche_client["portefeuille_pct"]
    cash = references.encaisse()
    poids = fiche_client.get("poids_par_classe_pct", {})
    zones = fiche_client["deduit"]["fourchettes_pct"]["valeur"]
    parts = [(CLASSES.get(c, c), float(w), COULEURS_CLASSES.get(c, COULEUR_AUTRE)) for c, w in poids.items()]
    lignes = "".join(C.ligne_zone(CLASSES.get(c, c), pct(float(w), 0), float(w), zones.get(c),
                                  COULEURS_CLASSES.get(c, COULEUR_AUTRE)) for c, w in poids.items())
    ordres = st.session_state.get(f"ordres_{persona}", [])
    faits = (f'<div><span>Liquidités</span><b>{C.e(dollars(pf.get(cash, 0.0) * valeur / 100))}</b></div>'
             f'<div><span>Positions</span><b>{len([t for t in pf if t != cash])}</b></div>'
             f'<div><span>Profil</span><b>{C.e(fiche_client["deduit"]["profil"]["libelle"])}</b></div>')
    if ordres:
        faits += f'<div><span>Ordres simulés</span><b>{len(ordres)}</b></div>'
    histoire = marche.valeur_du_portefeuille(pf, valeur)
    allure = C.courbe(histoire, 600, 110, BLEU_CLAIR, remplie=True, epaisseur=2.2)
    note = (f'<span class="note">Sur {marche.PERIODE}, avec le portefeuille d\'aujourd\'hui</span>' if histoire else "")
    sombre = (f'<div class="glc-sombre">{note}<p class="glc-etiquette">Valeur du portefeuille</p>'
              f'<div class="glc-chiffre">{C.e(dollars(valeur))}</div>'
              f'<p style="margin:2px 0 0 0">{C.variation(marche.variation(histoire), marche.PERIODE)}</p>'
              f'<div class="glc-faits">{faits}</div>{allure}</div>')
    clair = ('<div class="glc-carte"><p class="glc-etiquette">Répartition, et zone permise par votre politique '
             f'de placement</p><div class="glc-repart"><div>{C.anneau(parts, 124)}</div>'
             f'<div class="lignes">{lignes}</div></div></div>')
    return f'<div class="glc-duo">{sombre}{clair}</div>'


def _face_a_la_politique(fiche: dict) -> None:
    etat_lieux = api.etat_des_lieux(fiche)
    if "erreur" in etat_lieux:
        st.error(etat_lieux["erreur"])
        return
    dans = etat_lieux["dans_la_politique"]
    statut = "Dans votre politique de placement" if dans else "Hors de votre politique de placement"
    decide = etat_lieux.get("dimension_min")
    lignes = []
    for angle in angles_du_bloc(etat_lieux):
        n = etat_lieux["notes"][angle]
        sans = n.get("sans_objet") or n.get("note") is None
        lignes.append({"nom": nom_angle(angle), "note": None if sans else n["note"],
                       "decide": angle == decide and not sans, "aide": AIDE_ANGLES.get(angle, "")})
    phrase = ""
    n = etat_lieux["notes"].get(decide) or {}
    if n.get("mesure_min") and n.get("note") is not None and n["note"] < 99.95:
        phrase = (f"Angle déterminant : {nom_angle(decide).lower()}. Sa mesure la plus basse : "
                  f"{libelle_mesure(decide, n['mesure_min'])}.")
    with st.container(key="carte_etat"):
        C.montrer(f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">'
                  f'<p class="glc-h2">Votre portefeuille sous chaque angle</p>'
                  f'{C.pastille(statut, "compatible" if dans else "en_tension")}</div>'
                  + (f'<p class="glc-sur" style="margin-bottom:10px">{C.e(phrase)}</p>' if phrase else "")
                  + C.angles(lignes, LIMITE, f"Le trait marque la note de passage ({LIMITE:g}). Sous ce trait, "
                                             "un angle sort de votre politique de placement."))


def _positions(persona: str, fiche_client: dict) -> None:
    valeur = etat.valeur_pf(persona)
    univers = instruments()
    pf = fiche_client["portefeuille_pct"]
    plus_gros = max([abs(w) for w in pf.values()] + [1.0])
    lignes = []
    for t, w in sorted(pf.items(), key=lambda x: -x[1]):
        i = univers.get(t, {})
        serie = marche.cours(t)
        hausse = (marche.variation(serie) or 0) >= 0
        lignes.append([f"<b>{C.e(t)}</b><br><span class='s'>{C.e(i.get('nom', ''))}</span>",
                       C.e(CLASSES.get(i.get("classe_politique", ""), "")),
                       C.courbe(serie, 96, 26, HAUSSE if hausse else BAISSE), C.variation(marche.variation(serie)),
                       C.barre(w, plus_gros) + C.e(pct(w)), C.e(dollars(w * valeur / 100))])
    with st.container(key="carte_positions"):
        C.montrer(C.h2("Positions", f"Cours et variation sur {marche.PERIODE}, en dollars canadiens.")
                  + C.tableau([("Titre", ""), ("Classe d'actif", ""), ("Cours", ""), ("Variation", "n"),
                               ("Part", "n"), ("Montant", "n")], lignes))
    ordres = st.session_state.get(f"ordres_{persona}", [])
    if ordres:
        colonnes = [("Opération", ""), ("Titre", ""), ("Type", ""), ("Verdict", ""), ("Part", "n"), ("Montant", "n")]
        lignes = [[C.e(o.get("Opération", "")), f"<b>{C.e(o.get('Titre', ''))}</b>", C.e(o.get("Type", "")),
                   C.pastille(o.get("Verdict", ""), o.get("code")), C.e(pct(o.get("Part (%)", 0))),
                   C.e(dollars(o.get("Montant ($ CA)", 0)))] for o in ordres]
        with st.container(key="carte_ordres"):
            C.montrer(C.h2("Ordres simulés", "Aucune transaction réelle n'a eu lieu.") + C.tableau(colonnes, lignes))


def afficher(persona: str, fiche: dict, fiche_client: dict) -> None:
    client = etat.client_enregistre(persona)
    C.montrer(C.titre_page("Portefeuille", f"{client['nom']} · {client['description']}"))
    nouveau = not client["exemple"]
    if nouveau:
        composer(persona)
    if "erreur" in fiche_client:
        st.error(fiche_client["erreur"])
        return
    C.montrer(_apercu(persona, fiche_client))
    _face_a_la_politique(fiche)
    _positions(persona, fiche_client)
    if not nouveau:
        composer(persona)
    C.suite("Continuer vers Négocier", "negocier", "suite_portefeuille")
