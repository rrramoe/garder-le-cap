"""Page « Profil » : la fiche du client, puis la politique de placement qui en découle."""

from __future__ import annotations

import hashlib

import streamlit as st

from interface import composants as C
from interface import etat
from interface.textes import (CHAMPS_Q, CLASSES, GROUPES_Q, NOM, PAGES, PHRASE_LIMITES, QUESTIONNAIRE, RUBRIQUES, THEMES, annees,
                              charger_reference, francais, libelle_option, libelle_theme_reponse, nombre, pct, source_courte)


# ---------------------------------------------------------------- la fiche

def fiche(persona: str, fiche_session: dict) -> None:
    enregistre = etat.client_enregistre(persona)
    with st.container(key="carte_fiche"):
        sur = "Changez une réponse : votre politique de placement suit, à droite."
        if not etat.fiche_complete(fiche_session):
            sur = "Répondez à chaque question : votre politique de placement s'écrit dès que la fiche est complète."
        C.montrer(C.etape_du_chemin(1, "Vous répondez") + C.h2("Votre fiche", sur))
        groupes = [(r, list(champs)) for r, champs in GROUPES_Q]
        restants = [c for c in CHAMPS_Q if not any(c in champs for _, champs in groupes)]
        groupes[-1][1].extend(restants)

        def rubrique(cle: str) -> None:
            nom, question = RUBRIQUES[cle]
            C.montrer(f'<p class="glc-rubrique">{C.e(nom)}<span>{C.e(question)}</span></p>')

        def liste(champ: str) -> None:
            st.selectbox(QUESTIONNAIRE[champ]["libelle"], list(QUESTIONNAIRE[champ]["options"]),
                         key=etat.cle_q(persona, champ), index=None, placeholder="Choisir",
                         format_func=lambda o, c=champ: libelle_option(c, o))

        # La fiche tient dans sa colonne : deux listes par rangée, rubrique par rubrique, puis les thèmes,
        # serrés, une ligne chacun.
        seules = [g for g in groupes if len(g[1]) == 1]
        for debut in range(0, len(seules), 2):
            for colonne, (cle, champs) in zip(st.columns(2, gap="small"), seules[debut:debut + 2]):
                with colonne:
                    rubrique(cle)
                    liste(champs[0])
        for cle, champs in [g for g in groupes if len(g[1]) > 1]:
            rubrique(cle)
            for debut in range(0, len(champs), 2):
                colonnes = st.columns(2, gap="small", vertical_alignment="bottom")
                for colonne, champ in zip(colonnes, champs[debut:debut + 2]):
                    with colonne:
                        liste(champ)
        rubrique("preferences")
        C.montrer(f'<p class="glc-sur">« Exclure » et « Obligatoire » sont des règles strictes ; les autres choix, '
                  "des préférences.</p>")
        echelle = list(QUESTIONNAIRE["echelle_themes"]["options"])
        for t, lib in THEMES.items():
            st.radio(lib, echelle, key=etat.cle_q(persona, "theme_" + t), horizontal=True,
                     format_func=libelle_theme_reponse)
        ecarts = etat.fiche_modifiee(persona, fiche_session)
        if ecarts and enregistre["exemple"]:  # un nouveau compte n'a pas de fiche d'origine à retrouver
            gauche, droite = st.columns([3, 1], vertical_alignment="center")
            gauche.caption("Fiche modifiée : " + " ; ".join(ecarts) + ".")
            droite.button("Revenir à la fiche d'origine", on_click=etat.reinitialiser, args=(persona,),
                          key=f"reinit_{persona}", width="stretch")


# ---------------------------------------------------------------- la politique de placement

def _sources_connues(fiche_client: dict) -> dict:
    connues = {}
    try:
        connues.update({k: {**v, "id": k} for k, v in charger_reference("sources").items() if isinstance(v, dict)})
    except Exception:
        pass
    connues.update({s["id"]: s for s in fiche_client.get("sources", [])})
    return connues


def _ligne_source(ids: list, connues: dict, utilisees: list) -> str:
    """« Source : … » en quelques mots ; une convention du service porte la marque « hypothèse »."""
    noms, hypothese = [], False
    for i in ids:
        s = connues.get(i)
        if not s:
            continue
        if i not in utilisees:
            utilisees.append(i)
        if s.get("nature") == "publie":
            nom = source_courte(s)
            if nom and nom not in noms:
                noms.append(nom)
        else:
            hypothese = True
    texte = ("Source : " if len(noms) == 1 else "Sources : ") + " · ".join(C.e(n) for n in noms) if noms else ""
    if hypothese:
        texte += C.marqueur("hypothèse") if texte else "Convention du service" + C.marqueur("hypothèse")
    return texte


def _ids(entree: dict) -> list:
    return [entree.get(k) for k in ("source", "regle", "hypothese") if entree.get(k) and entree.get(k) != "questionnaire"]


def articles_de_la_politique(fiche_client: dict) -> tuple[list[str], list[str], dict]:
    """Les articles de la politique de placement, les sources citées et leur détail."""
    d, q = fiche_client["deduit"], fiche_client["questionnaire"]
    connues, utilisees, articles = _sources_connues(fiche_client), [], []

    numero = [0]

    def ajouter(nom: str, corps: str, ids: list | None = None) -> None:
        numero[0] += 1
        articles.append(C.article(numero[0], nom, corps, _ligne_source(ids or [], connues, utilisees)))

    def p(texte: str) -> str:
        return f"<p>{C.e(texte)}</p>"

    def rubrique(cle: str) -> None:
        nom, question = RUBRIQUES[cle]
        articles.append(f'<div class="glc-rubrique-doc">{C.e(nom)}<span>{C.e(question)}</span></div>')

    def liste(valeurs: list) -> str:
        if not valeurs:
            return p("Aucune.")
        return "<ul>" + "".join(
            f"<li>{C.e(libelle_theme_reponse(c['reponse']))} : {C.e(THEMES.get(c['theme'], c['theme']))}</li>"
            if isinstance(c, dict) else f"<li>{C.e(c)}</li>" for c in valeurs) + "</ul>"

    profil = d["profil"]

    rubrique("objectif")
    corps = p(libelle_option("objectif", q["objectif"]) + ".")
    if d.get("coherence_objectif", {}).get("valeur") == "a_verifier":
        corps += p(f"À vérifier : cet objectif s'accorde mal avec le profil {profil['libelle']}.")
    ajouter("Objectif", corps)

    rubrique("horizon")
    horizon = d.get("horizon_annees", {}).get("valeur")
    corps = p(libelle_option("horizon", q["horizon"]) + ".")
    if horizon:
        corps += p(f"Les calculs retiennent {annees(horizon, 0)}, la durée la plus courte de cet horizon.")
    ajouter("Horizon de placement", corps)

    rubrique("risque")
    ajouter("Profil d'investisseur", p(profil["libelle"] + ".") + (p(profil["phrase"]) if profil.get("phrase") else ""),
            _ids(profil))
    try:  # limites de risque du profil, telles que publiées
        limites = charger_reference("limites_risque")
        cle = profil["valeur"]
        pire, bande = limites["pire_annee_banque_pct"], limites["bandes_volatilite_pct"]
        corps = p(f"Pire année : une perte de {pct(abs(pire['par_profil'][cle]), 2)} au plus.")
        b = bande["par_profil"][cle]
        if b.get("max") is None:
            corps += p(f"Fluctuations : {pct(b['min'], 0)} par an et plus (niveau « {b['niveau']} »), sans plafond.")
        else:
            corps += p(f"Fluctuations : de {nombre(b['min'], 0)} à {pct(b['max'], 0)} par an (niveau « {b['niveau']} »).")
        ajouter("Limites de risque", corps, [pire.get("source"), bande.get("source")])
    except Exception:
        pass

    rubrique("contraintes")
    zones = d["fourchettes_pct"]["valeur"]
    lignes = [[C.e(CLASSES.get(c, c)), C.e(pct(f["min"], 0)), f"<b>{C.e(pct(f['cible'], 0))}</b>", C.e(pct(f["max"], 0))]
              for c, f in zones.items()]
    ajouter("Répartition stratégique",
            C.tableau([("Classe d'actif", ""), ("Minimum", "n"), ("Cible", "n"), ("Maximum", "n")], lignes),
            _ids(d["fourchettes_pct"]))
    liquidite = d.get("besoin_liquidite_pct", {})
    if liquidite.get("phrase"):
        ajouter("Réserve de liquidités", p(liquidite["phrase"]), _ids(liquidite))
    plafonds, crypto = d.get("plafonds_concentration_pct", {}), d.get("crypto_pct", {})
    corps, ids = "", []
    if plafonds.get("valeur"):
        v = plafonds["valeur"]
        corps += p(f"Au plus {pct(v['action_individuelle'], 0)} dans une action, {pct(v['secteur'], 0)} dans un secteur, "
                   f"{pct(v['fonds_negocie_en_bourse'], 0)} dans un fonds.")
        ids += _ids(plafonds)
    if crypto.get("valeur"):
        v = crypto["valeur"]
        corps += p(f"Cryptoactifs : cible de {pct(v['cible_pct'], 1)}, maximum de {pct(v['plafond_pct'], 1)}.")
        ids += _ids(crypto)
    if corps:
        ajouter("Concentration", corps, ids)
    ajouter("Expérience", p(libelle_option("experience", q["experience"]) + "."))
    ajouter("Règles strictes", liste(d.get("contraintes_strictes", {}).get("valeur") or []))

    rubrique("preferences")
    ajouter("Préférences", liste(d.get("preferences_souples", {}).get("valeur") or []))
    return articles, utilisees, connues


def politique(persona: str, fiche_client: dict, empreinte: str) -> None:
    nom = etat.client_enregistre(persona)["nom"]
    articles, utilisees, connues = articles_de_la_politique(fiche_client)
    profil = fiche_client["deduit"]["profil"]["libelle"]
    # La carte change de clé quand la politique change : elle se redessine alors avec une courte pulsation.
    with st.container(key=f"politique_{empreinte}"):
        C.montrer(C.document("Politique de placement", f"Écrite pour {nom}, sur mesure · profil {profil}", articles,
                             C.etape_du_chemin(2, f"{NOM} écrit")))
    publiees = [connues[i] for i in utilisees if connues[i].get("nature") == "publie"]
    conventions = [connues[i] for i in utilisees if connues[i].get("nature") != "publie"]
    with st.expander("Références"):
        if publiees:
            C.montrer('<p class="glc-etiquette">Sources publiées</p><ul>'
                      + "".join(f"<li>{C.e(francais(s['libelle']))} — {C.e(francais(s['source']))}</li>" for s in publiees) + "</ul>")
        if conventions:
            C.montrer('<p class="glc-etiquette">Conventions du service, marquées « hypothèse »</p><ul>'
                      + "".join(f"<li>{C.e(francais(s['libelle']))}</li>" for s in conventions) + "</ul>")


def empreinte_de(fiche_client: dict | None) -> str:
    """Ce qui change quand la politique de placement change : la clé de sa carte et du passage qui y mène."""
    if not fiche_client or "erreur" in fiche_client:
        return "attente"
    return hashlib.md5(repr(sorted(fiche_client["questionnaire"].items(), key=str)).encode("utf-8")).hexdigest()[:8]


def fiche_a_completer(page: str) -> None:
    """Le portefeuille et l'ordre attendent la fiche : sans elle, pas de politique de placement à respecter."""
    C.montrer(C.titre_page(PAGES.get(page, ""), "Cette page s'ouvre quand votre fiche est complète."))
    with st.container(key="carte_a_completer"):
        gauche, droite = st.columns([3, 1], vertical_alignment="center")
        with gauche:
            C.montrer('<p class="glc-h2">Commencez par votre fiche</p><p class="glc-sur">Six questions, puis vos '
                      "préférences. Le service en tire votre politique de placement.</p>")
        droite.button("Remplir ma fiche", key="vers_fiche", type="primary", width="stretch",
                      on_click=etat.aller, args=("profil",))


def afficher(persona: str, fiche_session: dict, fiche_client: dict | None) -> None:
    """Un chemin, visible dès l'arrivée : la fiche à gauche, le passage, la politique de placement à droite."""
    C.montrer(C.titre_page("Profil", "Vous répondez à gauche. Votre politique de placement s'écrit à droite, "
                                     f"sur mesure : tout ce que fait {NOM} s'appuie sur elle."))
    empreinte = empreinte_de(fiche_client)
    gauche, milieu, droite = st.columns([1, 0.085, 1.02], gap="small")
    with gauche:
        fiche(persona, fiche_session)
    with milieu, st.container(key=f"passage_{empreinte}"):
        # Le passage change de clé avec la politique : la lumière y court plus fort quand une réponse change.
        C.montrer(C.passage(len(RUBRIQUES)) + C.lien("Votre fiche devient votre politique de placement"))
    with droite:
        if fiche_client is None:
            manquantes = [QUESTIONNAIRE[c]["libelle"] for c in CHAMPS_Q if fiche_session["questionnaire"].get(c) is None]
            C.montrer(f'<div class="glc-vide">{C.etape_du_chemin(2, f"{NOM} écrit")}<h3>Politique de placement</h3>'
                      f'<p>Elle apparaîtra ici dès que la fiche sera complète. Il reste : '
                      f'{C.e(", ".join(manquantes).lower())}.</p></div>')
        elif "erreur" in fiche_client:
            st.error(fiche_client["erreur"])
        else:
            politique(persona, fiche_client, empreinte)
    if fiche_client is not None and "erreur" not in fiche_client:
        C.suite("Continuer vers le portefeuille", "portefeuille", "suite_profil")
