"""Page « Négocier » : le billet d'ordre, et l'analyse de l'ordre avant de le passer."""

from __future__ import annotations

import queue
import re
import threading
import time

import altair as alt
import pandas as pd
import streamlit as st

from moteur import api, references
from interface import composants as C
from interface import etat, marche
from interface.theme import BAISSE, BORD, ENCRE, FILET, GRIS, HAUSSE, POLICE, POSITIF, TENSION
from interface.textes import (AIDE_ANGLES, ANGLES_DEFAUT, AVIS_SANS_AGENT, BOUTON_ACTION, BOUTON_PASSER, CORRECTION_TEXTE,
                              DEJA_FAITE, DELAI_MAX_AGENT_S, DEPUIS_PRECEDENT, DIRECTIONS_TEXTE, EN_DIRECT_AGENT, EQUIPE, LIBELLES_OUTILS,
                              LIBELLES_PHASES, LIMITE, MESURES, NOM, OPERATIONS, SOLIDITE_TEXTE, STATUTS_REGLE, THEMES, TITRE_ANALYSE, TRACE,
                              TITRE_ETAPES, TYPES_ORDRE, VERIFICATION_TEXTE, angles_du_bloc, decrire_mesure,
                              derniers_prix_cad, dollars, francais, instruments, libelle_mesure, libelle_option,
                              libelle_theme_reponse, mesures_a_plat, nom_agent, nom_angle, nom_instrument, nombre,
                              note_txt, pct, pct_frac, phrase_execution, raison_courte)


# ---------------------------------------------------------------- le billet d'ordre

def billet(persona: str, fiche: dict) -> None:
    univers = instruments()
    prix = derniers_prix_cad()
    valeur = etat.valeur_pf(persona)
    pf = st.session_state[f"pf_{persona}"]
    cash = references.encaisse()

    with st.container(key="carte_billet"):
        C.montrer(C.h2("Ordre"))
        st.selectbox("Titre", list(univers), key=f"o_{persona}_ticker",
                     format_func=lambda t: f"{t} — {univers[t]['nom']}")
        st.radio("Opération", list(OPERATIONS), key=f"o_{persona}_operation", horizontal=True,
                 format_func=lambda k: OPERATIONS[k]["libelle"])
        ticker = st.session_state[f"o_{persona}_ticker"]
        operation = st.session_state[f"o_{persona}_operation"]
        serie = marche.cours(ticker)
        if serie and prix.get(ticker):
            hausse = (marche.variation(serie) or 0) >= 0
            C.montrer(f'<div class="glc-cours"><span><b>{C.e(dollars(prix[ticker], 2))}</b> '
                      f'{C.variation(marche.variation(serie), marche.PERIODE)}</span>'
                      f'{C.courbe(serie, 110, 34, HAUSSE if hausse else BAISSE)}</div>')
        sens = OPERATIONS[operation]["sens"]

        st.number_input("Montant ($ CA)", min_value=100.0, max_value=float(valeur), step=500.0,
                        key=f"o_{persona}_montant", format="%.0f")
        montant = float(st.session_state[f"o_{persona}_montant"])
        pourcentage = round(montant / valeur * 100, 4)
        st.caption(f"{pct(pourcentage)} de votre portefeuille ({dollars(valeur)})")

        c1, c2 = st.columns(2)
        c1.selectbox("Type d'ordre", list(TYPES_ORDRE), key=f"o_{persona}_type",
                     format_func=lambda k: TYPES_ORDRE[k]["libelle"])
        type_ordre = st.session_state[f"o_{persona}_type"]
        prix_ordre = None
        dernier = prix.get(ticker)
        if TYPES_ORDRE[type_ordre]["prix"]:
            cle_prix = f"o_{persona}_prix_{ticker}_{type_ordre}"
            st.session_state.setdefault(cle_prix, round(dernier, 2) if dernier else 1.0)
            c2.number_input(TYPES_ORDRE[type_ordre]["prix"], min_value=0.01, step=1.0, key=cle_prix, format="%.2f")
            prix_ordre = float(st.session_state[cle_prix])

        detenu = pf.get(ticker, 0.0) * valeur / 100
        deja = f"Vous détenez {dollars(detenu)} de {ticker}." if detenu > 0 else f"Vous ne détenez pas de {ticker}."
        if OPERATIONS[operation].get("aide"):
            aide = OPERATIONS[operation]["aide"]
        elif sens == "achat":
            aide = f"Liquidités disponibles : {dollars(pf.get(cash, 0.0) * valeur / 100)}."
        else:
            aide = "Une vente est versée dans vos liquidités."
        st.caption(f"{TYPES_ORDRE[type_ordre]['aide']} {aide} {deja}")

        analyser = st.button(BOUTON_ACTION, type="primary", key="inspecter", width="stretch")
        passer = st.button(BOUTON_PASSER, key="passer", width="stretch")

        details = {"operation": operation, "montant": montant, "type": type_ordre, "prix": prix_ordre,
                   "hypothese_execution": phrase_execution(type_ordre, prix_ordre)}
        if analyser:
            ancien = st.session_state.get(f"rapport_{persona}")
            if ancien is not None:
                st.session_state[f"precedent_{persona}"] = ancien
            st.session_state[f"rapport_{persona}"] = etat.analyser_par_le_moteur(persona, fiche, ticker, sens,
                                                                                 pourcentage, details)
            st.session_state.pop(f"message_{persona}", None)

        if passer and etat.operation_moteur(operation) != "comptant":
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
                    "Verdict": r["verdict"]["libelle"], "code": r["verdict"]["code"]}]
                st.session_state[f"message_{persona}"] = (
                    "ok", f"{OPERATIONS[operation]['nom']} de {dollars(montant)} de {ticker} "
                          f"({TYPES_ORDRE[type_ordre]['libelle'].lower()}) ajouté au portefeuille de cette session. "
                          f"Verdict : {r['verdict']['libelle'].lower()}. Aucune transaction réelle n'a eu lieu.")
                st.rerun()

        message = st.session_state.get(f"message_{persona}")
        if message:
            {"ok": st.success, "info": st.info}.get(message[0], st.error)(message[1])


# ---------------------------------------------------------------- l'analyse : verdict et angles

def _texte_ordre(o: dict, valeur: float) -> str:
    nom_op = OPERATIONS.get(o.get("operation", o["sens"]), {}).get("nom", o["sens"].capitalize())
    montant = o.get("montant", o["pourcentage"] * valeur / 100)
    return f"{nom_op} de {dollars(montant)} de {nom_instrument(o['ticker'])} · {pct(o['pourcentage'])} du portefeuille"


def bloc_verdict(sim: dict, rapport: dict, valeur: float) -> None:
    v, d = sim["verdict"], sim["direction"]
    if v["code"] == "incompatible":
        suite = "Une règle stricte passe avant les notes."
    else:
        suite = DIRECTIONS_TEXTE.get(d["cas"], d.get("libelle", ""))
    C.montrer(C.carte_verdict(_texte_ordre(rapport["ordre"], valeur), v["libelle"], v["code"],
                              raison_courte(sim), suite))


def bloc_angles(sim: dict) -> None:
    """Les angles, chacun avec sa note ; l'angle déterminant est marqué : c'est lui qui décide."""
    apres, avant = sim["apres"], sim.get("avant", {})
    regle = sim["verdict"]["code"] == "incompatible"  # une règle stricte décide alors, pas un angle
    lignes = []
    for angle in angles_du_bloc(apres):
        n1, n0 = apres["notes"][angle], avant.get("notes", {}).get(angle, {})
        sans = n1.get("sans_objet") or n1.get("note") is None
        lignes.append({"nom": nom_angle(angle), "note": None if sans else n1["note"],
                       "avant": None if sans else n0.get("note"),
                       "decide": angle == apres.get("dimension_min") and not sans and not regle,
                       "aide": n1.get("question") or AIDE_ANGLES.get(angle, "")})
    legende = f"Le trait marque la note de passage ({LIMITE:g}). "
    legende += ("Ici, une règle stricte décide du verdict, avant les notes." if regle
                else "L'angle déterminant, le plus bas, décide du verdict.")
    with st.container(key="carte_angles"):
        C.montrer(C.h2("Les angles de l'analyse") + C.angles(lignes, LIMITE, legende))


def bloc_a_retenir(sim: dict) -> None:
    """Ce qui complète le verdict, une phrase par point : solidité, part du risque, opération avancée."""
    points = []
    op = sim.get("operation") or {}
    if op.get("code") not in (None, "comptant"):
        ce = op.get("controle_experience", {})
        exp = libelle_option("experience", ce.get("experience", "intermediaire"))
        nom = op["libelle"].lower()
        if ce.get("effet") == "contrainte_stricte":
            points.append(("Expérience.", f"Votre expérience ({exp}) exclut la {nom}."))
        elif ce.get("effet") == "preference_souple":
            points.append(("Expérience.", f"Votre expérience ({exp}) : la {nom} est à éviter. "
                                          f"Note : {note_txt(ce.get('note'))} sur 100."))
        if op.get("levier_apres") is not None:
            points.append((f"Levier : {nombre(op['levier_apres'], 2)}.",
                           f"Votre exposition serait de {nombre(op['exposition_brute_apres_pct'], 0)} $ "
                           "pour 100 $ qui vous appartiennent."))
    attention = [p for p in sim.get("points_attention") or [] if p.get("type") == "operation"]
    if attention:
        points.append(("Point d'attention.", attention[0]["texte"]))
    if sim["verdict"]["code"] != "incompatible":
        c = sim.get("contribution_risque_apres")
        if c and c.get("part_du_risque_pct") is not None and abs(c.get("poids_pct") or 0) >= 0.05:
            if c["poids_pct"] < 0:  # vente à découvert
                points.append(("Part du risque.", f"La position à découvert sur {c['ticker']} "
                               f"({pct(-c['poids_pct'], 0)} du portefeuille) porterait "
                               f"{pct(c['part_du_risque_pct'], 0)} de son risque."))
            else:
                lien = "mais" if c["part_du_risque_pct"] > 1.25 * c["poids_pct"] else "et"
                points.append(("Part du risque.", f"{c['ticker']} ferait {pct(c['poids_pct'], 0)} du portefeuille, "
                               f"{lien} {pct(c['part_du_risque_pct'], 0)} de son risque."))
        solidite = sim.get("solidite")
        if solidite and solidite.get("statut") in SOLIDITE_TEXTE:
            points.append((f"{solidite['libelle']} :", SOLIDITE_TEXTE[solidite["statut"]]))
    if points:
        C.montrer('<div class="glc-carte"><p class="glc-h2" style="margin-bottom:6px">À retenir</p>'
                  + "".join(f'<p style="margin:0 0 4px 0"><b>{C.e(t)}</b> {C.e(x)}</p>' for t, x in points) + "</div>")


def bloc_changements(rapport: dict, precedent: dict | None) -> None:
    """Lecture avant/après entre deux analyses : ce qui a bougé et pourquoi."""
    if not precedent:
        return
    s0, s1 = precedent["simulation"], rapport["simulation"]
    if "erreur" in s0 or "erreur" in s1:
        return
    changements = etat.ecarts_questionnaire(precedent["fiche"]["questionnaire"], rapport["fiche"]["questionnaire"])
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
    lignes = [[C.e(nom_angle(cle[0])), C.e(libelle_mesure(*cle)), str(round(a0[cle])), f"<b>{round(a1[cle])}</b>"]
              for cle in a1 if cle in a0 and abs(a1[cle] - a0[cle]) >= 0.05]
    corps = (f'<p class="glc-h2">{C.e(DEPUIS_PRECEDENT)}</p>'
             f'<p class="glc-sur" style="margin-bottom:8px">Changé : {C.e(" ; ".join(changements))}.</p>'
             f'<p style="margin:0">{C.e(s0["verdict"]["libelle"])} → <b>{C.e(s1["verdict"]["libelle"])}</b></p>')
    if not lignes:
        corps += '<p class="glc-sur">Aucune mesure n\'a bougé.</p>'
    with st.container(key="carte_changements"):
        C.montrer(corps)
        if lignes:
            with st.expander(f"Les mesures qui ont bougé ({len(lignes)})"):
                C.montrer(C.tableau([("Angle", ""), ("Mesure", ""), ("Avant", "n"), ("Maintenant", "n")], lignes))


# ---------------------------------------------------------------- l'analyse : ce qui est possible

def _jambe(o: dict, valeur: float) -> str:
    """« Achat de 3 750 $ de XIU.TO »."""
    return (f"{str(o.get('sens', 'achat')).capitalize()} de "
            f"{dollars(float(o.get('pourcentage', 0)) * valeur / 100)} de {o.get('ticker')}")


def graphique_courbe(taille: dict, valeur: float) -> alt.Chart:
    df = pd.DataFrame(taille["courbe"])
    df["mesure"] = [libelle_mesure(d, m) for d, m in zip(df["dimension_min"], df["mesure_min"])]
    df["montant"] = [dollars(t * valeur / 100) for t in df["taille_pct"]]
    df["montant_cad"] = df["taille_pct"] * valeur / 100
    haut = max(100.0, float(df["score"].max()))
    base = alt.Chart(df).encode(
        x=alt.X("montant_cad:Q", title="Montant de l'ordre ($ CA)", scale=alt.Scale(domainMin=0),
                axis=alt.Axis(grid=False, tickCount=6, labelExpr="replace(format(datum.value, ',.0f'), /,/g, ' ')")),
        y=alt.Y("score:Q", title="Note de l'angle déterminant", scale=alt.Scale(domain=[0, haut])),
        tooltip=[alt.Tooltip("montant:N", title="Montant"),
                 alt.Tooltip("taille_pct:Q", title="Part (%)", format=".1f"),
                 alt.Tooltip("score:Q", title="Note de l'angle déterminant", format=".0f"),
                 alt.Tooltip("mesure:N", title="Mesure")])
    zone = alt.Chart(pd.DataFrame({"y": [0], "y2": [LIMITE]})).mark_rect(color=TENSION, opacity=0.10).encode(
        y="y:Q", y2="y2:Q")
    ligne = base.mark_line(color=ENCRE, strokeWidth=2)
    passage = alt.Chart(pd.DataFrame({"y": [LIMITE]})).mark_rule(color=ENCRE, strokeDash=[4, 4]).encode(y="y:Q")
    couches = [zone, ligne, passage]
    if taille.get("taille_compatible_pct") is not None:
        x_tc = float(taille["taille_compatible_pct"]) * valeur / 100
        couches.append(alt.Chart(pd.DataFrame({"x": [x_tc]})).mark_rule(color=POSITIF, strokeWidth=3).encode(x="x:Q"))
    return (alt.layer(*couches).properties(height=220)
            .configure(font=POLICE).configure_view(stroke=None)
            .configure_axis(labelColor=GRIS, titleColor=GRIS, gridColor=FILET, domainColor=BORD,
                            tickColor=BORD, labelFontSize=12, titleFontSize=12, titleFontWeight="normal"))


def _est_le_montant_reduit(piste: dict, ordre: dict, taille_pct: float) -> bool:
    """Vrai si cette piste des agents est le même ordre, sur le même titre, au montant compatible du moteur."""
    jambes = piste.get("ordres") or []
    if piste.get("famille") == "montant_reduit" and len(jambes) <= 1:
        return True
    return (len(jambes) == 1 and jambes[0].get("ticker") == ordre["ticker"]
            and jambes[0].get("sens", ordre["sens"]) == ordre["sens"]
            and abs(float(jambes[0].get("pourcentage", 0)) - float(taille_pct)) < 0.26)


def bloc_possible(rapport: dict, valeur: float) -> None:
    """« Ce qui est possible » : les pistes testées par le moteur, dans un seul tableau."""
    taille, agent = rapport.get("taille"), rapport.get("agent") or {}
    o = rapport["ordre"]
    nom_op = OPERATIONS.get(o.get("operation", o["sens"]), {}).get("nom", o["sens"].capitalize())
    phrase, lignes = "", []
    if not taille or "erreur" in taille:
        phrase = "La recherche d'un montant compatible n'a pas pu être faite."
    elif not taille.get("lancee", True):
        phrase = "Aucun autre montant n'est proposé. Changer le montant ne règle pas une règle stricte."
    else:
        issue, tc = taille.get("issue"), taille.get("taille_compatible_pct")
        if issue == "compatible_tel_quel":
            phrase = f"L'ordre est compatible tel quel ({dollars(taille['taille_demandee_pct'] * valeur / 100)})."
        elif issue == "compatible_avec_ajustement" and tc is not None:
            phrase = f"Pour devenir compatible : {dollars(tc * valeur / 100)} ou moins ({pct(tc)} du portefeuille)."
            cause = rapport["simulation"].get("cause") or {}
            if cause.get("mesure") and cause.get("phrase"):
                phrase += (f" La mesure qui décide : {libelle_mesure(cause.get('dimension'), cause['mesure'])} "
                           f"({francais(cause['phrase'])}).")
            # La même piste n'est montrée qu'une fois : si les agents ont testé ce montant réduit, leur ligne,
            # qui porte la raison, suffit.
            if not any(_est_le_montant_reduit(p, o, tc) for p in agent.get("pistes") or []):
                lignes.append(["<b>Montant réduit</b>",
                               C.e(f"{nom_op} de {dollars(tc * valeur / 100)} de {o['ticker']}"),
                               C.pastille("Compatible", "compatible"), ""])
        else:
            phrase = (f"Aucun montant jusqu'à {dollars(taille['taille_demandee_pct'] * valeur / 100)} "
                      f"({pct(taille['taille_demandee_pct'])}) ne garde tous les angles à {LIMITE:g} ou plus.")
    for p in agent.get("pistes") or []:
        v = p.get("verdict") or {}
        jambes = "<br>".join(C.e(_jambe(j, valeur)) for j in p.get("ordres") or [])
        nom = f"<b>{C.e(p.get('libelle_famille') or p.get('libelle') or 'Piste')}</b>"
        if p.get("raison"):
            nom += f"<br><span class='s'>{C.e(francais(p['raison']))}</span>"
        angle = francais((p.get("angle_le_plus_faible") or {}).get("libelle", ""))
        lignes.append([nom, jambes, C.pastille(v.get("libelle", ""), v.get("code")),
                       f"<span class='s'>{C.e(angle)}</span>" if v.get("code") != "compatible" else ""])
    s = agent.get("substitut")
    if s and s.get("verdict") and not agent.get("pistes"):
        part = s.get("pourcentage") or o["pourcentage"]
        lignes.append(["<b>Autre titre</b>", C.e(f"{nom_op} de {dollars(part * valeur / 100)} de {nom_instrument(s['ticker'])}"),
                       C.pastille(s["verdict"].get("libelle", ""), s["verdict"].get("code")), ""])
    corps = C.h2("Ce qui est possible") + f'<p style="margin:4px 0 10px 0">{C.e(phrase)}</p>'
    if agent.get("intention"):
        corps += (f'<p class="glc-sur" style="margin-bottom:10px">Finalité supposée de l\'ordre '
                  f'(hypothèse de l\'agent) : {C.e(francais(agent["intention"]))}</p>')
    explorateur = next((a for a in agent.get("agents") or [] if a.get("nom") == "explorateur"), None)
    if explorateur and explorateur.get("statut") == "repli" and explorateur.get("avis"):
        corps += f'<p class="glc-sur" style="margin-bottom:10px">{C.e(explorateur["avis"])}</p>'
    if lignes:
        corps += C.tableau([("Piste testée", ""), ("Ordre", "nb"), ("Verdict", ""), ("Angle déterminant", "")], lignes)
        if agent.get("pistes"):
            corps += ('<p class="glc-legende">Pistes choisies par l\'agent explorateur sous le mandat du chef de '
                      "dossier, puis calculées par le moteur. Ce ne sont pas des recommandations.</p>")
        elif len(lignes) > 1:
            corps += '<p class="glc-legende">Des pistes calculées par le moteur. Ce ne sont pas des recommandations.</p>'
        else:
            corps += '<p class="glc-legende">Une piste calculée par le moteur. Ce n\'est pas une recommandation.</p>'
    with st.container(key="carte_possible"):
        C.montrer(corps)
        if taille and taille.get("courbe") and taille.get("lancee", True):
            with st.expander("La note selon le montant"):
                st.altair_chart(graphique_courbe(taille, valeur), width="stretch")
                st.caption(f"Note de l'angle déterminant selon le montant de l'ordre. La zone colorée est sous la "
                           f"note de passage ({LIMITE:g})."
                           + (" Le trait vertical marque le montant compatible."
                              if taille.get("taille_compatible_pct") is not None else ""))


# ---------------------------------------------------------------- l'analyse : explication et détails

def paragraphes_explication(texte: str) -> list[tuple[str, str]]:
    """Le texte de l'agent en paragraphes titrés : [(titre, texte)]. Un texte sans titre garde un titre vide."""
    texte = re.sub(r"(?m)^#{1,6}\s+(.+?)\s*$", r"**\1.**", texte.strip())
    morceaux = re.split(r"\*\*(.+?)\*\*", texte)
    sortie = []
    if morceaux[0].strip():
        sortie.append(("", morceaux[0].strip()))
    for titre, corps in zip(morceaux[1::2], morceaux[2::2]):
        corps = corps.strip().lstrip(":").strip()
        sortie.append((titre.strip().rstrip(".:").strip(), corps))
    return sortie


def bloc_explication(rapport: dict) -> None:
    agent = rapport.get("agent") or {}
    if agent.get("erreur") or not agent.get("explication"):
        st.info(AVIS_SANS_AGENT + ".")
        return
    corps = C.h2("Explication") + '<div class="glc-explication" style="margin-top:10px">'
    for titre, texte in paragraphes_explication(agent["explication"]):
        corps += (f'<p class="t">{C.e(titre)}</p>' if titre else "") + (f"<p>{C.e(francais(texte))}</p>" if texte else "")
    corps += "</div>"
    statut = (agent.get("ancrage") or {}).get("statut")
    if statut in VERIFICATION_TEXTE:
        corps += C.coche(VERIFICATION_TEXTE[statut], ok=statut == "appuyee")
    else:
        corps += C.coche("Texte rédigé par l'agent à partir des calculs. Aucun chiffre ne vient du modèle de langage.")
    if (agent.get("correction") or {}).get("faite"):
        corps += f'<p class="glc-legende" style="margin-top:4px">{C.e(CORRECTION_TEXTE)}</p>'
    with st.container(key="carte_explication"):
        C.montrer(corps)


def controles(agent: dict) -> list[str]:
    """Ce que les contrôles ont relevé sur l'explication, en français simple, pour les étapes repliées."""
    a = agent.get("ancrage") or {}
    lignes = []
    if a.get("chiffres_non_sources"):
        lignes.append("chiffres absents des calculs : " + ", ".join(a["chiffres_non_sources"]))
    gf = agent.get("garde_fou") or {}
    if gf.get("actif"):
        lignes.append("garde-fou actif" + (", il est intervenu" if gf.get("intervenu") else ""))
    elif gf.get("avis"):
        lignes.append(gf["avis"])
    return lignes


def libelle_etape(t: dict) -> str:
    """Ce que l'agent a fait à cette étape, en une phrase."""
    if t.get("libelle"):
        return t["libelle"]
    outil = t.get("outil") or ""
    return LIBELLES_OUTILS.get(outil, f"J'appelle l'outil « {outil.replace('_', ' ')} ».")


def section_etapes(rapport: dict) -> None:
    """Les étapes, regroupées par agent, dans l'ordre. Sans agent : les appels au moteur faits par le service."""
    agent = rapport.get("agent") or {}
    if agent.get("trace") and not agent.get("erreur"):
        trace = agent["trace"]
    else:
        trace = rapport["trace_moteur"]
        st.caption("Sans l'agent, le service a appelé le moteur de calcul lui-même.")
    lignes, dernier = [], None
    for t in trace:
        qui = nom_agent(t["agent"]) if t.get("agent") else ""
        detail = (t.get("arguments") or {}).get("raison", "") if isinstance(t.get("arguments"), dict) else ""
        lignes.append({"libelle": libelle_etape(t), "agent": qui if qui != dernier else "", "fini": True,
                       "detail": detail})
        dernier = qui
    C.montrer(C.etapes(lignes))
    releves = controles(agent) if agent.get("trace") and not agent.get("erreur") else []
    if releves:
        st.caption("Contrôles : " + " ; ".join(releves) + ".")


def section_regles(sim: dict) -> None:
    cs = sim["contraintes_strictes"]
    if not cs.get("detail"):
        st.markdown("Aucune règle stricte dans votre profil.")
        return
    lignes = []
    for d in cs["detail"]:
        statut = STATUTS_REGLE.get(d["statut"], d["statut"])
        if d.get("controle") == "experience_operation":
            op = sim.get("operation") or {}
            exp = libelle_option("experience", op.get("controle_experience", {}).get("experience", "debutante"))
            lignes.append(f"<li><b>{C.e(op.get('libelle', d['theme']))}</b> — exclue pour l'expérience « {C.e(exp)} ».</li>")
            continue
        theme = THEMES.get(d["theme"], d["theme"])
        texte = f"<li><b>{C.e(libelle_theme_reponse(d['reponse']))} : {C.e(theme)}</b> — {C.e(statut)}."
        decl = d.get("declencheur") or {}
        if isinstance(decl, dict) and decl.get("preuve"):
            # La date de la preuve reste dans les sources.
            texte += " Preuve : " + C.e(re.sub(r",? (?:fiche )?du \d{1,2} \S+ \d{4}", "", decl["preuve"]))
        lignes.append(texte + "</li>")
    C.montrer("<ul>" + "".join(lignes) + "</ul>")


def section_mesures(sim: dict) -> None:
    """Chaque angle et ses mesures, avant et après l'ordre."""
    for angle in angles_du_bloc(sim["apres"]):
        n0, n1 = sim["avant"]["notes"].get(angle, {}), sim["apres"]["notes"][angle]
        titre = f'<p class="glc-etiquette" style="color:var(--encre);margin:12px 0 4px 0">{C.e(nom_angle(angle))}'
        if n1.get("question"):
            titre += f' <span style="font-weight:400;color:var(--gris)">· {C.e(n1["question"])}</span>'
        titre += "</p>"
        if n1.get("sans_objet") or n1.get("note") is None:
            raison = f" ({n1['raison']})" if n1.get("raison") else ""
            C.montrer(titre + f'<p class="glc-sur">sans objet{C.e(raison)}</p>')
            continue
        lignes = []
        for cle, m1 in n1["mesures"].items():
            if not isinstance(m1, dict):
                continue
            m0 = n0.get("mesures", {}).get(cle, {})
            avant = str(round(m0["note"])) if isinstance(m0.get("note"), (int, float)) else "—"
            apres = f"<b>{round(m1['note'])}</b>" if isinstance(m1.get("note"), (int, float)) else "—"
            lignes.append([C.e(libelle_mesure(angle, cle)), f"<span class='s'>{C.e(decrire_mesure(angle, cle, m1))}</span>",
                           avant, apres])
        C.montrer(titre + C.tableau([("Mesure", ""), ("Après l'ordre", ""), ("Avant", "n"), ("Après", "n")], lignes))
    signalements = [sg.get("message", "") for angle in angles_du_bloc(sim["apres"])
                    for sg in sim["apres"]["notes"][angle].get("signalements", [])]
    for message in signalements:
        st.caption(f"Signalement : {message}")
    st.caption(f"Chaque mesure est notée de 0 à 100 ; {LIMITE:g} est la note de passage. "
               "La note d'un angle est celle de sa mesure la plus basse.")


def section_solidite(solidite: dict | None) -> None:
    """Le même calcul refait sur deux périodes : une mauvaise année de marché, puis le reste."""
    if not solidite or not solidite.get("fenetres"):
        st.caption("Solidité non calculée.")
        return
    lignes = []
    for f in solidite["fenetres"].values():
        cote = "respecte la politique de placement" if f["dans_la_politique"] else f"sous la note de passage ({LIMITE:g})"
        angle = f" ({nom_angle(f['dimension_min']).lower()})" if f.get("dimension_min") else ""
        texte = f"{C.e(f['libelle'])} : note de l'angle déterminant{C.e(angle)} {note_txt(f.get('score'))}, {cote}."
        absentes = [MESURES.get(m, str(m).replace("_", " ")) for m in f.get("mesures_indeterminees") or []]
        if absentes:
            texte += f" Période trop courte pour mesurer : {C.e(', '.join(absentes))}."
        lignes.append(f"<li>{texte}</li>")
    tete = f"<p>{C.e(francais(solidite['explication']))}</p>" if solidite.get("explication") else ""
    C.montrer(tete + "<ul>" + "".join(lignes) + "</ul>")
    st.caption("Les notes affichées plus haut restent celles de toute la période.")


def _phrases_profil(fiche_client: dict) -> list[str]:
    """Phrases simples des règles du profil qui changent l'analyse (profil retenu, liquidités)."""
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

    def bloc(titre: str, lignes: list[str]) -> str:
        if not lignes:
            return ""
        return (f'<p class="glc-etiquette" style="color:var(--encre);margin:12px 0 2px 0">{C.e(titre)}</p><ul>'
                + "".join(f"<li>{C.e(l)}</li>" for l in lignes) + "</ul>")

    enregistre = etat.client_enregistre(persona)
    origine_valeur = "montant fictif" if enregistre["exemple"] else "montant saisi à l'écran"
    periode = rapport["simulation"].get("periode", {})
    limites = []
    indet = [THEMES.get(k, k) for k, v in rapport["fiche_instrument"].get("etiquettes", {}).items()
             if v.get("valeur") == "indetermine"]
    if indet:
        limites.append(f"Thème(s) inconnu(s) pour {rapport['ordre']['ticker']} : {', '.join(indet)}.")
    limites += list((rapport["simulation"].get("operation") or {}).get("limites", []))
    limites += ["Cinq ans d'historique ne contiennent pas toutes les crises possibles.",
                "Le service vérifie la compatibilité avec votre politique de placement. Il ne juge pas la qualité "
                "du placement et ne remplace pas un conseiller."]
    origine = api.origine_references()
    C.montrer(
        bloc("Votre profil", _phrases_profil(rapport["fiche_client"]))
        + bloc("Sources publiées", [francais(f"{s['libelle']} — {s['source']}") for s in publies])
        + bloc("Hypothèses", [francais(s["libelle"]) for s in hypotheses]
               + [f"Valeur du portefeuille de {enregistre['nom']} : {dollars(etat.valeur_pf(persona))}, {origine_valeur}.",
                  rapport["ordre"].get("hypothese_execution", "L'analyse suppose que l'ordre est exécuté.")])
        + bloc("Scénarios", [f"Les notes de risque rejouent l'historique du {periode.get('debut', '?')} au "
                             f"{periode.get('fin', '?')}, en {periode.get('devise', 'CAD')}, comme si le portefeuille "
                             "avait existé tel quel. C'est le passé, pas une prévision."])
        + bloc("Limites", limites)
        + (bloc("Fichiers de référence", [origine["message"]]) if origine.get("message") else ""))


# ---------------------------------------------------------------- analyse en direct

def lignes_en_direct(etapes: list[dict]) -> list[dict]:
    """Les étapes telles qu'on les montre pendant l'analyse : la phrase, et l'agent quand il change."""
    lignes, dernier = [], None
    for x in etapes:
        qui = nom_agent(x["agent"]) if x.get("agent") else ""
        lignes.append({"libelle": x["libelle"], "agent": qui if qui != dernier else "", "fini": x["fini"]})
        dernier = qui or dernier
    return lignes


def analyser_en_direct(rapport: dict) -> bool:
    """Fait travailler l'agent en montrant chaque étape au moment où elle se passe.

    L'agent tourne dans un fil à part ; son crochet `sur_etape` ne fait que déposer les événements dans une
    file. Seul le fil du script touche à l'affichage. Renvoie False si l'agent ne sait pas annoncer ses
    étapes : l'appelant garde alors un simple indicateur d'attente.
    """
    try:
        from agent.inspection import inspecter
    except Exception:
        return False
    if not etat.accepte_sur_etape(inspecter):
        return False

    file: queue.Queue = queue.Queue()
    sortie: dict = {}
    o = rapport["ordre"]
    relancer = bool(rapport.pop("relancer", False))

    def travail():
        sortie["r"] = etat.appeler_agent(rapport["fiche"], o["ticker"], o["sens"], o["pourcentage"],
                                         etat.operation_moteur(o.get("operation")), sur_etape=file.put,
                                         relancer=relancer)

    fil = threading.Thread(target=travail, name="analyse-agent", daemon=True)
    debut = time.monotonic()
    fil.start()
    etapes: list[dict] = []  # outils et phases, dans l'ordre où ils arrivent
    par_numero: dict = {}

    def clore_phases():
        for x in etapes:
            if x.get("phase") and not x["fini"]:
                x["fini"] = True

    zone = st.empty()
    zone.markdown(C.en_direct(EN_DIRECT_AGENT, lignes_en_direct(etapes)), unsafe_allow_html=True)
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
            x = {"libelle": ev.get("libelle") or libelle_etape({"outil": ev.get("outil")}),
                 "agent": ev.get("agent"), "fini": False}
            etapes.append(x)
            par_numero[ev.get("etape", len(etapes))] = x
        elif moment == "fin_outil":
            x = par_numero.get(ev.get("etape")) or next(
                (y for y in reversed(etapes) if not y["fini"] and not y.get("phase")), None)
            if x is not None:
                x["fini"] = True
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
        zone.markdown(C.en_direct(EN_DIRECT_AGENT, lignes_en_direct(etapes)), unsafe_allow_html=True)
    r = sortie.get("r")
    if r is None:
        r = {"explication": None, "trace": [], "erreur": "l'agent a dépassé le temps prévu"}
    # Chaque étape de la trace garde la phrase annoncée en direct et le nom de l'agent qui l'a faite.
    outils_vus = [x for x in etapes if not x.get("phase")]
    for i, t in enumerate(r.get("trace") or []):
        if not isinstance(t, dict):
            continue
        x = par_numero.get(t.get("etape")) or (outils_vus[i] if i < len(outils_vus) else None)
        if x:
            t.setdefault("libelle", x["libelle"])
            if x.get("agent") and not t.get("agent"):
                t["agent"] = x["agent"]
    rapport["agent"] = r
    zone.empty()
    return True


def numero_de_trace(agent: dict) -> str | None:
    """Le numéro de la trace gardée de cette analyse, s'il y en a une."""
    trace = agent.get("trace_aws") if isinstance(agent, dict) else None
    return str(trace["id"]) if isinstance(trace, dict) and trace.get("id") else None


def bloc_deja_faite(persona: str, rapport: dict) -> None:
    """Une ligne discrète au-dessus du résultat : le numéro de la trace de l'analyse, et, quand les agents
    rendent une analyse déjà faite pour cet ordre, de quoi la relancer."""
    agent = rapport.get("agent") or {}
    memoire = agent.get("memoire") or {}
    numero = numero_de_trace(agent)
    deja = memoire.get("statut") == "deja_faite"
    if not deja and not numero:
        return
    lignes = ([memoire.get("message") or DEJA_FAITE] if deja else []) + ([TRACE.format(id=numero)] if numero else [])
    with st.container(key="deja_faite"):
        gauche, droite = st.columns([5, 1], vertical_alignment="center")
        gauche.caption(" ".join(lignes))
        if deja:
            droite.button("Relancer", key="relancer", type="tertiary", on_click=etat.relancer_l_analyse,
                          args=(persona,))


# ---------------------------------------------------------------- l'analyse, de haut en bas

def analyse(persona: str, rapport: dict, fiche_actuelle: dict) -> None:
    sim = rapport["simulation"]
    valeur = etat.valeur_pf(persona)
    if rapport["fiche"] != fiche_actuelle:
        st.warning(f"Votre profil ou votre portefeuille a changé. Cliquez sur « {BOUTON_ACTION} » "
                   "pour mettre l'analyse à jour.")
    if "erreur" in sim:
        st.error(sim["erreur"])
        return
    exp = rapport["fiche_client"].get("questionnaire", {}).get("experience", "intermediaire")
    ouvert = exp == "avancee"

    bloc_deja_faite(persona, rapport)
    bloc_verdict(sim, rapport, valeur)
    bloc_angles(sim)
    bloc_a_retenir(sim)
    bloc_changements(rapport, st.session_state.get(f"precedent_{persona}"))

    if rapport.get("agent") is None:
        # Les agents travaillent : leurs étapes se montrent ici, puis la page se redessine avec leur apport.
        if not analyser_en_direct(rapport):
            with st.spinner("L'agent rédige l'explication…"):
                o = rapport["ordre"]
                rapport["agent"] = etat.appeler_agent(rapport["fiche"], o["ticker"], o["sens"], o["pourcentage"],
                                                      etat.operation_moteur(o.get("operation")),
                                                      relancer=bool(rapport.pop("relancer", False)))
        st.rerun()

    bloc_possible(rapport, valeur)
    bloc_explication(rapport)
    with st.expander(TITRE_ETAPES, expanded=False):
        section_etapes(rapport)
    with st.expander("Les mesures de chaque angle, avant et après", expanded=False):
        section_mesures(sim)
    with st.expander("Règles strictes", expanded=sim["verdict"]["code"] == "incompatible"):
        section_regles(sim)
    if sim["verdict"]["code"] != "incompatible":
        with st.expander("Solidité du résultat", expanded=False):
            section_solidite(sim.get("solidite"))
    with st.expander("Sources, hypothèses et limites", expanded=False):
        section_sources(rapport, persona)
    st.caption("Vous décidez. L'analyse renseigne ; elle ne bloque rien et ne conseille rien.")


def afficher(persona: str, fiche: dict) -> None:
    client = etat.client_enregistre(persona)
    C.montrer(C.titre_page("Négocier", f"{client['nom']} · analysez un ordre avant de le passer."))
    gauche, droite = st.columns([4.3, 7.7], gap="large")
    with gauche:
        billet(persona, fiche)
    # L'analyse est ce que le service ajoute au courtage : sa zone porte la lueur, plus vive pendant qu'elle tourne.
    with droite, st.container(key="zone_sigma"):
        C.montrer(C.etiquette_du_service(f"L'analyse {NOM}", EQUIPE))
        rapport = st.session_state.get(f"rapport_{persona}")
        if rapport is not None:
            analyse(persona, rapport, fiche)
        else:
            C.montrer(C.etat_vide(TITRE_ANALYSE, f"Cliquez sur « {BOUTON_ACTION} » pour savoir si cet ordre respecte "
                                  "votre politique de placement, avant de le passer.",
                                  [nom_angle(a) for a in ANGLES_DEFAUT]))
    C.suite("Comprendre l'analyse : Aide", "aide", "suite_negocier", principal=False)
