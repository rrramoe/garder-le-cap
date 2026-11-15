"""Garder le cap : interface locale (Streamlit) de l'inspection d'ordres.

Lancement : streamlit run app.py --server.address localhost

Le code calcule, le modèle explique : tous les chiffres affichés viennent de
moteur.api. L'agent (agent/inspection.py), s'il est présent, n'ajoute que
l'explication et la trace de ses appels.
"""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from moteur import api

RACINE = Path(__file__).resolve().parent
BANDEAU = ("Simulation à but éducatif. Aucune transaction réelle. "
           "Ceci n'est pas un conseil financier personnalisé.")
AVIS_SANS_AGENT = ("Explication de l'agent indisponible : le rapport ci-dessous vient "
                   "directement du moteur de calcul")
LIMITE = 50

COULEURS_VERDICT = {"compatible": "#2e7d32", "en_tension": "#b26a00", "incompatible": "#c62828"}
CLASSES = {"liquidites": "Liquidités", "revenu_fixe": "Revenu fixe", "actions": "Actions",
           "alternatifs": "Titres alternatifs"}
DIMENSIONS = {"risque": "Risque", "diversification": "Diversification", "preferences": "Préférences"}
MESURES = {
    "ampleur": "ampleur de la pire baisse",
    "duree": "durée sous l'eau",
    "classe_liquidites": "poids des liquidités",
    "classe_revenu_fixe": "poids du revenu fixe",
    "classe_actions": "poids des actions",
    "classe_alternatifs": "poids des titres alternatifs",
    "crypto": "poids des cryptoactifs",
    "plus_grosse_action": "plus grosse action",
    "plus_gros_fonds": "plus gros fonds négocié en bourse",
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
    "reste_dans_la_politique": "Le portefeuille était dans la politique et y reste.",
    "fait_sortir_de_la_politique": "Le portefeuille était dans la politique ; l'ordre l'en fait sortir.",
    "hors_politique_rapproche": "Le portefeuille était déjà hors politique ; l'ordre l'en rapproche.",
    "hors_politique_aggrave": "Le portefeuille était déjà hors politique ; l'ordre aggrave l'écart.",
}
STATUTS_CONTRAINTE = {"violee": "violée", "respectee": "respectée", "signalee": "signalée",
                      "ignoree": "ignorée", "non_applicable": "non applicable"}
NIVEAUX = {"essentiel": "essentiel", "standard": "standard", "detaille": "détaillé"}
SOURCES_LOCALES = {"questionnaire": "Votre réponse au questionnaire"}


# ---------------------------------------------------------------- références

@st.cache_data
def charger_reference(nom: str) -> dict:
    return json.loads((RACINE / "reference" / f"{nom}.json").read_text(encoding="utf-8"))


QUESTIONNAIRE = charger_reference("questionnaire")
THEMES = {t["id"]: t["libelle"] for t in charger_reference("themes")["themes"]}
PERSONAS = charger_reference("personas")["personas"]
ORDRE_PERSONAS = ["robert", "mateo", "amira"]


@st.cache_data
def instruments() -> dict:
    r = api.lister_instruments()
    return {i["symbole"]: i for i in r.get("instruments", [])}


@st.cache_data
def fiche_instrument(ticker: str) -> dict:
    return api.lire_fiche_instrument(ticker)


# ---------------------------------------------------------------- formats

def nombre(x: float, d: int = 1) -> str:
    texte = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return texte.replace("-", "−")


def pct(x: float, d: int = 1) -> str:
    """x est déjà en % (15 = 15 %)."""
    return f"{nombre(x, d)} %"


def pct_frac(x: float, d: int = 1) -> str:
    """x est une fraction (−0,18 = −18 %)."""
    return pct(x * 100, d)


def note_txt(x: float | None) -> str:
    return "—" if x is None else nombre(x, 1)


def libelle_option(champ: str, cle: str) -> str:
    opt = QUESTIONNAIRE[champ]["options"][cle]
    return opt if isinstance(opt, str) else opt["libelle"]


def libelle_theme_reponse(cle: str) -> str:
    return QUESTIONNAIRE["echelle_themes"]["options"][cle]["libelle"]


def libelle_mesure(dimension: str, cle: str) -> str:
    if dimension == "preferences":
        return f"thème « {THEMES.get(cle, cle)} »"
    return MESURES.get(cle, cle)


def nom_instrument(ticker: str) -> str:
    i = instruments().get(ticker)
    return f"{ticker} ({i['nom']})" if i else ticker


def secteur_fr(s: str) -> str:
    return SECTEURS.get(s, s)


def decrire_mesure(dimension: str, cle: str, m: dict) -> str:
    """Une phrase avec les chiffres d'une mesure, tels que le moteur les donne."""
    if cle == "ampleur" and dimension == "risque":
        return (f"pire baisse de {pct_frac(m['pire_baisse'])} sur la période, contre "
                f"{pct_frac(m['pire_baisse_reference'])} pour le portefeuille de référence du profil "
                f"et {pct_frac(m['pire_baisse_limite'])} pour son portefeuille limite")
    if cle == "duree" and dimension == "risque":
        texte = (f"{nombre(m['temps_sous_l_eau_annees'])} ans sous l'eau "
                 f"(du {m.get('debut', '?')} au {m.get('fin', '?')}) pour un horizon de "
                 f"{nombre(m['horizon_annees'], 0)} ans")
        if m.get("non_recupere"):
            texte += " ; la baisse n'est pas récupérée à la fin des données"
        return texte
    if cle.startswith("classe_"):
        return (f"{pct(m['poids'])} du portefeuille (fourchette {nombre(m['min'], 0)} à "
                f"{pct(m['max'], 0)}, cible {pct(m['cible'], 0)})")
    if cle == "crypto" and dimension == "diversification":
        return f"{pct(m['poids'])} du portefeuille (plafond du profil : {pct(m['plafond'], 0)})"
    if cle in ("plus_grosse_action", "plus_gros_fonds"):
        if not m.get("ticker"):
            return "aucune position de ce type"
        return f"{m['ticker']} pèse {pct(m['poids'])} (plafond : {pct(m['plafond'], 0)})"
    if cle == "plus_gros_secteur":
        if not m.get("secteur"):
            return "aucune action individuelle"
        return f"{secteur_fr(m['secteur'])} pèse {pct(m['poids'])} (plafond : {pct(m['plafond'], 0)})"
    if dimension == "preferences":
        if "poids_expose" in m:
            texte = f"{pct(m['poids_expose'])} du portefeuille dans ce thème à éviter"
            if m.get("instruments"):
                texte += " (" + ", ".join(f"{t} {pct(w)}" for t, w in m["instruments"].items()) + ")"
            if m.get("etiquette_indeterminee"):
                texte += ("; étiquette indéterminée pour "
                          + ", ".join(m["etiquette_indeterminee"]))
            return texte
        if "poids_vendu" in m:
            return f"{pct(m['poids_vendu'])} vendu dans ce thème recherché"
    return m.get("libelle", "")


def mesures_a_plat(bloc: dict) -> dict:
    """{(dimension, mesure): note} pour comparer deux inspections."""
    sortie = {}
    for dim, n in bloc.get("notes", {}).items():
        for cle, m in n.get("mesures", {}).items():
            if isinstance(m, dict) and "note" in m:
                sortie[(dim, cle)] = m["note"]
    return sortie


# ---------------------------------------------------------------- état de session

def cle_q(persona: str, champ: str) -> str:
    return f"q_{persona}_{champ}"


def initialiser(persona: str) -> None:
    p = PERSONAS[persona]
    q = p["questionnaire"]
    for champ in ("objectif", "horizon", "fluctuations", "experience"):
        st.session_state.setdefault(cle_q(persona, champ), q[champ])
    for theme in THEMES:
        st.session_state.setdefault(cle_q(persona, "theme_" + theme), q["themes"].get(theme, "neutre"))
    st.session_state.setdefault(f"pf_{persona}", {t: float(w) for t, w in p["portefeuille_pct"].items()})
    ordre = p.get("ordre_demo", {})
    st.session_state.setdefault(f"o_{persona}_ticker", ordre.get("ticker", "XIU.TO"))
    st.session_state.setdefault(f"o_{persona}_sens", ordre.get("sens", "achat"))
    st.session_state.setdefault(f"o_{persona}_pct", float(ordre.get("pourcentage", 5)))


def reinitialiser(persona: str) -> None:
    for cle in list(st.session_state.keys()):
        if cle.startswith((f"q_{persona}_", f"pf_{persona}", f"o_{persona}_",
                           f"rapport_{persona}", f"precedent_{persona}", f"message_{persona}")):
            del st.session_state[cle]


def fiche_session(persona: str) -> dict:
    s = st.session_state
    return {
        "persona": persona,
        "questionnaire": {
            "objectif": s[cle_q(persona, "objectif")],
            "horizon": s[cle_q(persona, "horizon")],
            "fluctuations": s[cle_q(persona, "fluctuations")],
            "experience": s[cle_q(persona, "experience")],
            "themes": {t: s[cle_q(persona, "theme_" + t)] for t in THEMES},
        },
        "portefeuille_pct": dict(s[f"pf_{persona}"]),
    }


def fiche_modifiee(persona: str, fiche: dict) -> list[str]:
    """Libellés des réponses qui diffèrent de la fiche d'origine du persona."""
    q0 = PERSONAS[persona]["questionnaire"]
    q = fiche["questionnaire"]
    ecarts = []
    for champ in ("objectif", "horizon", "fluctuations", "experience"):
        if q[champ] != q0[champ]:
            ecarts.append(f"{QUESTIONNAIRE[champ]['libelle']} : {libelle_option(champ, q[champ])}")
    for t in THEMES:
        if q["themes"][t] != q0["themes"].get(t, "neutre"):
            ecarts.append(f"{THEMES[t]} : {libelle_theme_reponse(q['themes'][t])}")
    return ecarts


def ecarts_questionnaire(q_avant: dict, q_apres: dict) -> list[str]:
    ecarts = []
    for champ in ("objectif", "horizon", "fluctuations", "experience"):
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
                f"{len(d['contraintes_strictes']['valeur'])} contrainte(s) stricte(s), "
                f"{len(d['preferences_souples']['valeur'])} préférence(s) souple(s).")
    if outil == "lire_fiche_instrument":
        vraies = [THEMES.get(k, k) for k, e in r.get("etiquettes", {}).items() if e.get("valeur") is True]
        return (f"{r['nom']}, classe {CLASSES.get(r['classe_politique'], r['classe_politique'])}, "
                f"volatilité annualisée {pct_frac(r['statistiques_cad']['volatilite_annualisee'])} en CAD ; "
                f"étiquettes vraies : {', '.join(vraies) if vraies else 'aucune'}.")
    if outil == "simuler_ordre":
        return (f"Verdict « {r['verdict']['libelle'].lower()} », score {note_txt(r['avant']['score'])} → "
                f"{note_txt(r['apres']['score'])}, donné par {DIMENSIONS[r['dimension_min']].lower()} "
                f"({libelle_mesure(r['dimension_min'], r['mesure_min'])}).")
    if outil == "chercher_taille_compatible":
        if not r.get("lancee", True):
            return f"Recherche non lancée : {r.get('raison', '')}"
        if r.get("taille_compatible_pct") is None:
            return "Aucune taille compatible jusqu'au montant demandé."
        return (f"Taille compatible : {pct(r['taille_compatible_pct'])} "
                f"({len(r.get('courbe', []))} tailles testées par pas de {pct(r['pas_pct'])}).")
    return ""


def inspecter_moteur(persona: str, fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    """Le rapport structuré, appelé directement sur moteur.api, avec la trace des appels."""
    trace = []
    client_affiche = persona if not fiche_modifiee(persona, fiche) and \
        fiche["portefeuille_pct"] == {t: float(w) for t, w in PERSONAS[persona]["portefeuille_pct"].items()} \
        else f"fiche de session ({PERSONAS[persona]['nom']})"

    def appel(outil, fonction, *args, **arguments):
        debut = time.perf_counter()
        r = fonction(*args)
        trace.append({"etape": len(trace) + 1, "outil": outil, "arguments": arguments,
                      "resultat_resume": resume_appel(outil, r), "resultat": r,
                      "duree_s": time.perf_counter() - debut})
        return r

    fiche_client = appel("lire_fiche_client", api.lire_fiche_client, fiche, client=client_affiche)
    fiche_instr = appel("lire_fiche_instrument", api.lire_fiche_instrument, ticker, ticker=ticker)
    simulation = appel("simuler_ordre", api.simuler_ordre, fiche, ticker, sens, pourcentage,
                       client=client_affiche, ticker=ticker, sens=sens, pourcentage=pourcentage)
    taille = None
    if "erreur" not in simulation:
        taille = appel("chercher_taille_compatible", api.chercher_taille_compatible, fiche, ticker, sens,
                       pourcentage, client=client_affiche, ticker=ticker, sens=sens, pourcentage=pourcentage)
    return {
        "ordre": {"ticker": ticker, "sens": sens, "pourcentage": pourcentage},
        "fiche": copy.deepcopy(fiche),
        "fiche_client": fiche_client,
        "fiche_instrument": fiche_instr,
        "simulation": simulation,
        "taille": taille,
        "trace_moteur": trace,
        "agent": None,  # rempli juste après l'affichage du rapport structuré
    }


def appeler_agent(fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    """Appelle l'agent s'il existe ; renvoie toujours un dict {explication, trace, erreur, ...}."""
    try:
        from agent.inspection import inspecter  # import paresseux : le module peut être absent
    except Exception:
        return {"explication": None, "trace": [], "erreur": "module de l'agent absent"}
    try:
        r = inspecter(copy.deepcopy(fiche), ticker, sens, pourcentage)
    except Exception as exc:  # l'agent ne doit jamais faire tomber le rapport
        return {"explication": None, "trace": [], "erreur": f"l'agent a échoué ({type(exc).__name__})"}
    if not isinstance(r, dict):
        return {"explication": None, "trace": [], "erreur": "réponse de l'agent illisible"}
    r.setdefault("trace", [])
    if not r.get("erreur") and not r.get("explication"):
        r["erreur"] = "aucune explication reçue"
    return r


# ---------------------------------------------------------------- graphiques

def graphique_classes(poids: dict, fourchettes: dict, titre: str) -> alt.Chart:
    lignes = []
    for cle, lib in CLASSES.items():
        f = fourchettes[cle]
        lignes.append({"classe": lib, "poids": float(poids.get(cle, 0.0)), "min": f["min"],
                       "max": f["max"], "cible": f["cible"],
                       "dans": f["min"] <= float(poids.get(cle, 0.0)) <= f["max"]})
    df = pd.DataFrame(lignes)
    ordre = list(CLASSES.values())
    y = alt.Y("classe:N", sort=ordre, title=None)
    bande = alt.Chart(df).mark_bar(color="#9e9e9e", opacity=0.25, size=26).encode(
        y=y, x=alt.X("min:Q", title="Poids dans le portefeuille (%)", scale=alt.Scale(domain=[0, 100])),
        x2="max:Q",
        tooltip=[alt.Tooltip("classe:N", title="Classe"), alt.Tooltip("min:Q", title="Minimum (%)"),
                 alt.Tooltip("max:Q", title="Maximum (%)")])
    barre = alt.Chart(df).mark_bar(size=10).encode(
        y=y, x="poids:Q",
        color=alt.Color("dans:N", scale=alt.Scale(domain=[True, False], range=["#37474f", "#c62828"]),
                        legend=None),
        tooltip=[alt.Tooltip("classe:N", title="Classe"), alt.Tooltip("poids:Q", title="Poids (%)", format=".1f")])
    cible = alt.Chart(df).mark_tick(color="#1565c0", thickness=2, size=30).encode(
        y=y, x="cible:Q", tooltip=[alt.Tooltip("cible:Q", title="Cible (%)")])
    return (bande + barre + cible).properties(title=titre, height=200)


def graphique_courbe(taille: dict) -> alt.Chart:
    df = pd.DataFrame(taille["courbe"])
    df["dimension"] = df["dimension_min"].map(lambda d: DIMENSIONS.get(d, d))
    df["mesure"] = [libelle_mesure(d, m) for d, m in zip(df["dimension_min"], df["mesure_min"])]
    haut = max(100.0, float(df["score"].max()))
    base = alt.Chart(df).encode(
        x=alt.X("taille_pct:Q", title="Taille de l'ordre (% du portefeuille)",
                scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1, format="d")),
        y=alt.Y("score:Q", title="Score après l'ordre (0 à 100)", scale=alt.Scale(domain=[0, haut])),
        tooltip=[alt.Tooltip("taille_pct:Q", title="Taille (%)", format=".1f"),
                 alt.Tooltip("score:Q", title="Score", format=".1f"),
                 alt.Tooltip("dimension:N", title="Donné par"), alt.Tooltip("mesure:N", title="Mesure")])
    ligne = base.mark_line(color="#37474f") + base.mark_circle(size=28, color="#37474f")
    limite = alt.Chart(pd.DataFrame({"y": [LIMITE]})).mark_rule(color="#c62828", strokeDash=[5, 4]).encode(y="y:Q")
    x_min, x_max = float(df["taille_pct"].min()), float(df["taille_pct"].max())
    # Étiquettes posées dans le cadre, avec un halo blanc pour rester lisibles sur la courbe.
    lim = pd.DataFrame({"y": [LIMITE], "x": [x_min], "lib": ["Limite de la politique (50)"]})
    couches = [ligne, limite] + _etiquette(lim, "#c62828", align="left", dy=12)
    if taille.get("taille_compatible_pct") is not None:
        x_tc = float(taille["taille_compatible_pct"])
        tc = pd.DataFrame({"x": [x_tc], "y": [haut * 0.94],
                           "lib": [f"Taille compatible : {pct(x_tc)}"]})
        couches.append(alt.Chart(tc).mark_rule(color="#2e7d32").encode(x="x:Q"))
        a_gauche = x_tc > (x_min + x_max) / 2
        couches += _etiquette(tc, "#2e7d32", align="right" if a_gauche else "left", dx=-6 if a_gauche else 6)
    return alt.layer(*couches).properties(height=280)


def _etiquette(df: pd.DataFrame, couleur: str, **pos) -> list:
    enc = {"x": "x:Q", "y": "y:Q", "text": "lib:N"}
    halo = alt.Chart(df).mark_text(fontSize=11, stroke="white", strokeWidth=4, **pos).encode(**enc)
    texte = alt.Chart(df).mark_text(fontSize=11, color=couleur, **pos).encode(**enc)
    return [halo, texte]


# ---------------------------------------------------------------- rendu : fiche

def libelle_source(source_id: str, sources: dict) -> str:
    if source_id in SOURCES_LOCALES:
        return SOURCES_LOCALES[source_id]
    s = sources.get(source_id)
    if not s:
        return source_id
    if s["nature"] == "publie":
        return f"Publié par {s['source']} ({s['date']})"
    return f"Hypothèse : {s['libelle']}"


def valeur_deduite(cle: str, e: dict) -> str:
    v = e["valeur"]
    if cle == "profil":
        return e.get("libelle", v)
    if cle == "horizon_annees":
        return f"{nombre(v, 0)} ans (borne basse)"
    if cle == "plafonds_concentration_pct":
        return (f"{pct(v['action_individuelle'], 0)} par action, {pct(v['secteur'], 0)} par secteur, "
                f"{pct(v['fonds_negocie_en_bourse'], 0)} par fonds négocié en bourse")
    if cle == "crypto_pct":
        return f"cible {pct(v['cible_pct'], 1)}, plafond {pct(v['plafond_pct'], 1)}"
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
    if cle == "niveau_detail":
        return NIVEAUX.get(v, v)
    if cle == "coherence_objectif":
        return {"coherent": "cohérent avec le profil", "a_verifier": "à vérifier"}.get(v, v)
    return str(v)


LIBELLES_DEDUIT = {
    "profil": "Profil d'investisseur",
    "fourchettes_pct": "Fourchettes par classe",
    "horizon_annees": "Horizon retenu pour les calculs",
    "plafonds_concentration_pct": "Plafonds de concentration",
    "crypto_pct": "Cryptoactifs",
    "contraintes_strictes": "Contraintes strictes",
    "preferences_souples": "Préférences souples",
    "niveau_detail": "Niveau de détail du rapport",
    "coherence_objectif": "Cohérence de l'objectif",
}


def onglet_fiche(persona: str, fiche_client: dict) -> None:
    st.subheader("Questionnaire")
    st.caption("Neuf réponses à choix. Toute modification s'applique aussitôt aux autres onglets.")
    c1, c2 = st.columns(2)
    for i, champ in enumerate(("objectif", "horizon", "fluctuations", "experience")):
        options = list(QUESTIONNAIRE[champ]["options"])
        (c1 if i % 2 == 0 else c2).selectbox(
            QUESTIONNAIRE[champ]["libelle"], options, key=cle_q(persona, champ),
            format_func=lambda o, c=champ: libelle_option(c, o))
    st.markdown("**Thèmes**")
    echelle = list(QUESTIONNAIRE["echelle_themes"]["options"])
    for t, lib in THEMES.items():
        st.radio(lib, echelle, key=cle_q(persona, "theme_" + t), horizontal=True,
                 format_func=libelle_theme_reponse)

    st.subheader("Ce qui en est déduit")
    if "erreur" in fiche_client:
        st.error(fiche_client["erreur"])
        return
    sources = {s["id"]: s for s in fiche_client.get("sources", [])}
    for cle, e in fiche_client["deduit"].items():
        lib = LIBELLES_DEDUIT.get(cle, cle)
        origine = libelle_source(e.get("source", ""), sources)
        if e.get("hypothese"):
            origine += " — " + libelle_source(e["hypothese"], sources)
        if cle == "fourchettes_pct":
            st.markdown(f"**{lib}**")
            df = pd.DataFrame([{"Classe": CLASSES[c], "Minimum (%)": f["min"], "Cible (%)": f["cible"],
                                "Maximum (%)": f["max"]} for c, f in e["valeur"].items()])
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.markdown(f"**{lib}** : {valeur_deduite(cle, e)}")
        st.caption(f"{e.get('origine', '')} {origine}.")


# ---------------------------------------------------------------- rendu : portefeuille

def onglet_portefeuille(persona: str, fiche: dict, fiche_client: dict) -> None:
    if "erreur" in fiche_client:
        st.error(fiche_client["erreur"])
        return
    profil = fiche_client["deduit"]["profil"]["libelle"]
    pf = fiche_client["portefeuille_pct"]
    if pf != {t: float(w) for t, w in PERSONAS[persona]["portefeuille_pct"].items()}:
        st.info("Ce portefeuille tient compte des ordres simulés passés pendant cette session.")

    st.subheader("Positions")
    univers = instruments()
    lignes = [{"Symbole": t, "Nom": univers.get(t, {}).get("nom", ""),
               "Classe": CLASSES.get(univers.get(t, {}).get("classe_politique", ""), ""),
               "Poids (%)": round(w, 2)} for t, w in sorted(pf.items(), key=lambda x: -x[1])]
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")

    st.subheader("Répartition par classe")
    st.altair_chart(graphique_classes(fiche_client["poids_par_classe_pct"],
                                      fiche_client["deduit"]["fourchettes_pct"]["valeur"],
                                      f"Poids actuels face aux fourchettes du profil {profil}"),
                    width="stretch")
    st.caption("Bande grise : fourchette du profil. Trait bleu : cible. Barre : poids actuel "
               "(en rouge s'il sort de la fourchette).")

    st.subheader("État des lieux, sans ordre")
    e = api.etat_des_lieux(fiche)
    if "erreur" in e:
        st.error(e["erreur"])
        return
    statut = "dans la politique" if e["dans_la_politique"] else "hors de la politique"
    st.markdown(f"Score du portefeuille actuel : **{note_txt(e['score'])} / 100**, soit **{statut}** "
                f"(limite : {LIMITE}). Il est donné par la note de "
                f"{DIMENSIONS[e['dimension_min']].lower()}, mesure « {libelle_mesure(e['dimension_min'], e['mesure_min'])} ».")
    for dim, n in e["notes"].items():
        if n.get("sans_objet"):
            st.markdown(f"- **{DIMENSIONS[dim]}** : sans objet (aucun thème à éviter ou à rechercher)")
            continue
        m = n["mesures"].get(n["mesure_min"], {})
        st.markdown(f"- **{DIMENSIONS[dim]}** : {note_txt(n['note'])} — "
                    f"{libelle_mesure(dim, n['mesure_min'])} : {decrire_mesure(dim, n['mesure_min'], m)}")
    p = e.get("periode", {})
    st.caption(f"Calculé sur l'historique du {p.get('debut', '?')} au {p.get('fin', '?')}, en "
               f"{p.get('devise', 'CAD')}.")


# ---------------------------------------------------------------- rendu : rapport

def bloc_verdict(sim: dict, taille: dict | None, niveau: str) -> None:
    v = sim["verdict"]
    couleur = COULEURS_VERDICT.get(v["code"], "#37474f")
    o = sim["ordre"]
    sens = "Achat" if o["sens"] == "achat" else "Vente"
    dim, mes = sim["dimension_min"], sim["mesure_min"]
    m = sim["apres"]["notes"][dim]["mesures"].get(mes, {})
    if v["code"] == "incompatible":
        phrase = ("Une contrainte stricte de la fiche est violée : rien ne la compense, quel que soit le score. "
                  f"Les notes, elles, donnent {note_txt(sim['score'])} / 100.")
    else:
        phrase = (f"Le score est donné par la note de {DIMENSIONS[dim].lower()}, mesure "
                  f"« {libelle_mesure(dim, mes)} » : {decrire_mesure(dim, mes, m)}.")
    st.markdown(
        f"""<div style="border-left: 6px solid {couleur}; padding: 0.6rem 1rem; margin: 0.5rem 0 1rem 0;">
<div style="font-size: 0.9rem; opacity: 0.8;">{sens} de {pct(o['pourcentage'])} du portefeuille en {nom_instrument(o['ticker'])}</div>
<div style="font-size: 1.6rem; font-weight: 600; color: {couleur};">{v['libelle']}</div>
<div style="font-size: 1.05rem;">Score après l'ordre : <b>{note_txt(sim['score'])} / 100</b> (limite de la politique : {LIMITE})</div>
</div>""", unsafe_allow_html=True)
    st.markdown(phrase)
    c = sim.get("contribution_risque_apres")
    if c and c.get("part_du_risque_pct") is not None:
        st.markdown(f"Après l'ordre, {c['ticker']} pèse {pct(c['poids_pct'])} du portefeuille "
                    f"et {pct(c['part_du_risque_pct'])} de son risque.")


def bloc_changements(rapport: dict, precedent: dict | None) -> None:
    """Lecture avant/après entre deux inspections : ce qui a bougé et pourquoi."""
    if not precedent:
        return
    s0, s1 = precedent["simulation"], rapport["simulation"]
    if "erreur" in s0 or "erreur" in s1:
        return
    changements_fiche = ecarts_questionnaire(precedent["fiche"]["questionnaire"], rapport["fiche"]["questionnaire"])
    o0, o1 = precedent["ordre"], rapport["ordre"]
    if o0 != o1:
        changements_fiche.insert(0, f"Ordre : {o0['sens']} {pct(o0['pourcentage'])} {o0['ticker']} → "
                                    f"{o1['sens']} {pct(o1['pourcentage'])} {o1['ticker']}")
    if precedent["fiche"]["portefeuille_pct"] != rapport["fiche"]["portefeuille_pct"]:
        changements_fiche.append("Portefeuille modifié par un ordre simulé")
    if not changements_fiche:
        return
    a0, a1 = mesures_a_plat(s0["apres"]), mesures_a_plat(s1["apres"])
    lignes = []
    for cle in a1:
        if cle in a0 and abs(a1[cle] - a0[cle]) >= 0.05:
            lignes.append({"Dimension": DIMENSIONS[cle[0]], "Mesure": libelle_mesure(*cle),
                           "Avant": round(a0[cle], 1), "Maintenant": round(a1[cle], 1),
                           "Écart": round(a1[cle] - a0[cle], 1)})
    with st.container(border=True):
        st.markdown("**Depuis l'inspection précédente**")
        st.markdown("Changé : " + " ; ".join(changements_fiche) + ".")
        st.markdown(f"Verdict : {s0['verdict']['libelle']} → **{s1['verdict']['libelle']}**. "
                    f"Score : {note_txt(s0['score'])} → **{note_txt(s1['score'])}**, donné par "
                    f"« {libelle_mesure(s1['dimension_min'], s1['mesure_min'])} » "
                    f"(avant : « {libelle_mesure(s0['dimension_min'], s0['mesure_min'])} »).")
        if lignes:
            st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
        else:
            st.markdown("Aucune mesure n'a bougé.")


def section_contraintes(sim: dict) -> None:
    st.markdown("#### 2. Contraintes strictes")
    cs = sim["contraintes_strictes"]
    if not cs.get("detail"):
        st.markdown("Aucune contrainte stricte dans la fiche (aucun thème « exclure » ou « obligatoire »).")
        return
    for d in cs["detail"]:
        statut = STATUTS_CONTRAINTE.get(d["statut"], d["statut"])
        theme = THEMES.get(d["theme"], d["theme"])
        texte = f"- **{libelle_theme_reponse(d['reponse'])} : {theme}** — {statut}. {d.get('raison', '')}"
        decl = d.get("declencheur") or {}
        if isinstance(decl, dict) and decl.get("preuve"):
            texte += f" Preuve : {decl['preuve']}"
        st.markdown(texte)


def section_notes(sim: dict, niveau: str) -> None:
    st.markdown("#### 3. Les trois notes, avant → après")
    lignes = []
    for dim in ("risque", "diversification", "preferences"):
        n0, n1 = sim["avant"]["notes"][dim], sim["apres"]["notes"][dim]
        sans_objet = n1.get("sans_objet")
        lignes.append({
            "Note": DIMENSIONS[dim],
            "Avant": None if sans_objet else round(n0["note"], 1),
            "Après": None if sans_objet else round(n1["note"], 1),
            "Mesure la plus faible après l'ordre": "sans objet" if sans_objet else libelle_mesure(dim, n1["mesure_min"]),
        })
    lignes.append({"Note": "Score (la plus faible)", "Avant": round(sim["avant"]["score"], 1),
                   "Après": round(sim["apres"]["score"], 1),
                   "Mesure la plus faible après l'ordre": libelle_mesure(sim["dimension_min"], sim["mesure_min"])})
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    st.caption("Chaque note va de 0 à 100 : 100 = sur la cible, 50 = limite de la politique. "
               "Une note est la plus faible de ses mesures ; le score est la plus faible des trois notes.")
    if niveau == "essentiel":
        return
    for dim in ("risque", "diversification", "preferences"):
        n0, n1 = sim["avant"]["notes"][dim], sim["apres"]["notes"][dim]
        if n1.get("sans_objet"):
            continue
        with st.expander(f"{DIMENSIONS[dim]} : le détail des mesures", expanded=(niveau == "detaille")):
            for cle, m1 in n1["mesures"].items():
                if not isinstance(m1, dict) or "note" not in m1:
                    continue
                m0 = n0["mesures"].get(cle, {})
                avant = note_txt(m0.get("note")) if m0 else "—"
                st.markdown(f"- **{libelle_mesure(dim, cle)}** : {avant} → **{note_txt(m1['note'])}** — "
                            f"{decrire_mesure(dim, cle, m1)}")
            if dim == "risque" and niveau == "detaille":
                st.markdown(f"- Volatilité annualisée du portefeuille : "
                            f"{pct_frac(n0['volatilite_annualisee'])} → {pct_frac(n1['volatilite_annualisee'])} "
                            "(affichée, non notée)")
            for s in n1.get("signalements", []):
                st.markdown(f"- Signalement : {s.get('message', '')}")


def section_direction(sim: dict) -> None:
    st.markdown("#### 4. Direction")
    d = sim["direction"]
    st.markdown(f"**{d['libelle']}.** {DIRECTIONS_TEXTE.get(d['cas'], '')} Score : "
                f"{note_txt(d['score_avant'])} → {note_txt(d['score_apres'])} (limite {LIMITE}).")
    if d.get("remarque"):
        st.caption(d["remarque"])


def section_possible(sim: dict, taille: dict | None) -> None:
    st.markdown("#### 5. Ce qui est possible")
    if not taille or "erreur" in taille:
        st.markdown("La recherche de taille n'a pas pu être faite"
                    + (f" : {taille['erreur']}" if taille and "erreur" in taille else "."))
        return
    if not taille.get("lancee", True):
        st.markdown(f"Aucune taille n'est proposée. {taille.get('raison', '')}")
        return
    issue = taille.get("issue")
    tc = taille.get("taille_compatible_pct")
    if issue == "compatible_tel_quel":
        st.markdown(f"L'ordre est compatible tel quel, à {pct(taille['taille_demandee_pct'])}.")
    elif issue == "compatible_avec_ajustement" and tc is not None:
        st.markdown(f"À **{pct(tc)}** du portefeuille au lieu de {pct(taille['taille_demandee_pct'])}, "
                    f"le score reste à {LIMITE} ou plus : l'ordre serait compatible à cette taille.")
    else:
        st.markdown(f"Aucune taille, par pas de {pct(taille['pas_pct'])} jusqu'à "
                    f"{pct(taille['taille_demandee_pct'])}, ne garde le score à {LIMITE} ou plus.")
    if taille.get("courbe"):
        st.altair_chart(graphique_courbe(taille), width="stretch")
        st.caption("Score du portefeuille après l'ordre selon sa taille. Sous la ligne rouge, l'ordre "
                   "dépasse une limite de la politique. Survolez un point pour voir la mesure qui le donne.")


def section_agent(rapport: dict) -> None:
    st.markdown("#### 6. Explication de l'agent")
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
    st.caption("Texte rédigé par l'agent à partir des résultats des outils ; aucun chiffre ne vient du "
               "modèle de langage. " + " ; ".join(details))


def section_etapes(rapport: dict, niveau: str) -> None:
    st.markdown("#### 7. Étapes de l'inspection")
    agent = rapport.get("agent") or {}
    if agent.get("trace") and not agent.get("erreur"):
        trace = agent["trace"]
        st.caption("Les outils appelés par l'agent, dans l'ordre.")
    else:
        trace = rapport["trace_moteur"]
        st.caption("Les appels au moteur de calcul faits par l'interface, dans l'ordre.")
    for i, t in enumerate(trace, start=1):
        args = ", ".join(f"{k}={v!r}" for k, v in (t.get("arguments") or {}).items())
        st.markdown(f"{t.get('etape', i)}. **`{t.get('outil', '?')}`**({args}) — {t.get('resultat_resume', '')}")
        if niveau == "detaille" and t.get("resultat") is not None:
            with st.expander(f"Résultat complet de l'étape {t.get('etape', i)}"):
                st.json(t["resultat"], expanded=False)


def section_sources(rapport: dict) -> None:
    st.markdown("#### 8. Sources, hypothèses et limites")
    sources = {}
    for r in (rapport["fiche_client"], rapport["fiche_instrument"], rapport["simulation"], rapport["taille"] or {}):
        for s in r.get("sources", []) if isinstance(r, dict) else []:
            sources[s["id"]] = s
    publies = [s for s in sources.values() if s["nature"] == "publie"]
    hypotheses = [s for s in sources.values() if s["nature"] != "publie"]
    st.markdown("**Faits publiés**")
    for s in publies:
        st.markdown(f"- {s['libelle']} — {s['source']} ({s['date']})")
    st.markdown("**Hypothèses du projet**")
    for s in hypotheses:
        st.markdown(f"- {s['libelle']} — {s['source']}")
    p = rapport["simulation"].get("periode", {})
    st.markdown("**Scénarios**")
    st.markdown(f"- Les notes de risque rejouent l'historique du {p.get('debut', '?')} au {p.get('fin', '?')}, "
                f"en {p.get('devise', 'CAD')}, comme si le portefeuille avait existé tel quel. "
                "C'est un scénario passé, pas une prévision.")
    st.markdown("**Limites**")
    indet = [THEMES.get(k, k) for k, e in rapport["fiche_instrument"].get("etiquettes", {}).items()
             if e.get("valeur") == "indetermine"]
    if indet:
        st.markdown(f"- Étiquette(s) indéterminée(s) pour {rapport['ordre']['ticker']} : {', '.join(indet)}.")
    st.markdown("- Cinq ans d'historique ne contiennent pas toutes les crises possibles.")
    st.markdown("- L'outil vérifie la compatibilité d'un ordre avec la politique de la fiche ; il ne juge "
                "pas la qualité du placement et ne remplace pas un conseiller.")


def afficher_rapport(persona: str, rapport: dict, fiche_actuelle: dict) -> None:
    sim = rapport["simulation"]
    st.divider()
    st.subheader("Rapport d'inspection")
    if rapport["fiche"] != fiche_actuelle:
        st.warning("La fiche a changé depuis cette inspection. Cliquez sur « Inspecter » pour mettre le "
                   "rapport à jour et voir ce qui a bougé.")
    if "erreur" in sim:
        st.error(sim["erreur"])
        return
    fc = rapport["fiche_client"]
    niveau = fc.get("deduit", {}).get("niveau_detail", {}).get("valeur", "standard")
    exp = fc.get("questionnaire", {}).get("experience", "intermediaire")
    st.caption(f"Niveau de détail : {NIVEAUX.get(niveau, niveau)} (expérience « {libelle_option('experience', exp)} »).")

    st.markdown("#### 1. Verdict et score")
    bloc_verdict(sim, rapport["taille"], niveau)
    bloc_changements(rapport, st.session_state.get(f"precedent_{persona}"))
    section_contraintes(sim)
    section_notes(sim, niveau)
    section_direction(sim)
    section_possible(sim, rapport["taille"])

    if rapport.get("agent") is None:
        with st.spinner("L'agent rédige l'explication à partir des résultats des outils…"):
            o = rapport["ordre"]
            rapport["agent"] = appeler_agent(rapport["fiche"], o["ticker"], o["sens"], o["pourcentage"])
    section_agent(rapport)
    section_etapes(rapport, niveau)
    section_sources(rapport)
    st.caption("Vous décidez. L'inspection ne bloque rien : le bouton « Passer l'ordre (simulé) » reste disponible.")


# ---------------------------------------------------------------- rendu : ordre

def onglet_ordre(persona: str, fiche: dict) -> None:
    univers = instruments()
    pf = st.session_state[f"pf_{persona}"]
    c1, c2, c3 = st.columns([3, 1.3, 1.3])
    c1.selectbox("Instrument", list(univers), key=f"o_{persona}_ticker",
                 format_func=lambda t: f"{t} — {univers[t]['nom']}")
    c2.radio("Sens", ["achat", "vente"], key=f"o_{persona}_sens", horizontal=True,
             format_func=lambda s: "Achat" if s == "achat" else "Vente")
    c3.number_input("Montant (% du portefeuille)", min_value=0.5, max_value=100.0, step=0.5,
                    key=f"o_{persona}_pct", format="%.1f")
    ticker = st.session_state[f"o_{persona}_ticker"]
    sens = st.session_state[f"o_{persona}_sens"]
    pourcentage = float(st.session_state[f"o_{persona}_pct"])
    st.caption(f"Un achat est payé par l'encaisse (ZST.TO : {pct(pf.get('ZST.TO', 0.0))} du portefeuille) ; "
               f"une vente y est versée. Position actuelle en {ticker} : {pct(pf.get(ticker, 0.0))}.")

    b1, b2, _ = st.columns([1, 1.4, 2])
    inspecter = b1.button("Inspecter", type="primary", key="inspecter", width="stretch")
    passer = b2.button("Passer l'ordre (simulé)", key="passer", width="stretch")

    if inspecter:
        ancien = st.session_state.get(f"rapport_{persona}")
        if ancien is not None:
            st.session_state[f"precedent_{persona}"] = ancien
        st.session_state[f"rapport_{persona}"] = inspecter_moteur(persona, fiche, ticker, sens, pourcentage)
        st.session_state.pop(f"message_{persona}", None)

    if passer:
        r = api.simuler_ordre(fiche, ticker, sens, pourcentage)
        if "erreur" in r:
            st.session_state[f"message_{persona}"] = ("erreur", r["erreur"])
        else:
            st.session_state[f"pf_{persona}"] = {t: float(w) for t, w in r["portefeuille_apres_pct"].items()}
            libelle = "Achat" if sens == "achat" else "Vente"
            st.session_state[f"message_{persona}"] = (
                "ok", f"{libelle} de {pct(pourcentage)} en {ticker} appliqué au portefeuille de cette session "
                      f"(verdict au moment de l'ordre : {r['verdict']['libelle'].lower()}). "
                      "Aucune transaction réelle n'a eu lieu.")
            st.rerun()

    message = st.session_state.get(f"message_{persona}")
    if message:
        (st.success if message[0] == "ok" else st.error)(message[1])

    rapport = st.session_state.get(f"rapport_{persona}")
    if rapport is not None:
        afficher_rapport(persona, rapport, fiche)
    else:
        st.markdown("Cliquez sur **Inspecter** pour vérifier si cet ordre est compatible avec la politique "
                    "de la fiche, avant de le passer.")


# ---------------------------------------------------------------- page

def main() -> None:
    st.set_page_config(page_title="Garder le cap", layout="wide")
    st.warning(BANDEAU)

    # Streamlit oublie l'état d'un widget non affiché : on garde celui des autres personas.
    for cle in list(st.session_state.keys()):
        if isinstance(cle, str) and cle.startswith(("q_", "o_")):
            st.session_state[cle] = st.session_state[cle]

    with st.sidebar:
        st.title("Garder le cap")
        st.caption("Inspection d'ordres avant transaction")
        persona = st.radio("Client", ORDRE_PERSONAS, key="persona",
                           format_func=lambda p: PERSONAS[p]["nom"])
    initialiser(persona)
    fiche = fiche_session(persona)
    fiche_client = api.lire_fiche_client(fiche)

    with st.sidebar:
        if "erreur" not in fiche_client:
            d = fiche_client["deduit"]
            st.markdown(f"Profil **{d['profil']['libelle']}** · horizon "
                        f"{nombre(d['horizon_annees']['valeur'], 0)} ans")
        ecarts = fiche_modifiee(persona, fiche)
        if ecarts:
            st.markdown("Fiche modifiée : " + " ; ".join(ecarts))
        st.button("Revenir à la fiche d'origine", on_click=reinitialiser, args=(persona,),
                  key=f"reinit_{persona}")
        st.divider()
        st.caption("L'outil parle de compatibilité avec la politique du client, jamais de la qualité "
                   "d'un placement. Il n'interdit rien et ne recommande rien.")

    st.title(f"{PERSONAS[persona]['nom']}")
    onglets = st.tabs(["Fiche", "Portefeuille", "Ordre"])
    with onglets[0]:
        onglet_fiche(persona, fiche_client)
    with onglets[1]:
        onglet_portefeuille(persona, fiche, fiche_client)
    with onglets[2]:
        onglet_ordre(persona, fiche)


main()
