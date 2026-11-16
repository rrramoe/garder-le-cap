"""L'ouverture du service : l'introduction en quelques panneaux, puis le choix d'un compte."""

from __future__ import annotations

import base64
import functools
from pathlib import Path

import streamlit as st

from moteur import api, references
from interface import composants as C
from interface import etat
from interface.theme import ENCRE, GRIS, OR, SAUGE
from interface.textes import (AIDE_ANGLES, BOUTON_ACTION, BOUTON_ESSAI, BOUTON_PASSER_INTRO, CHAMPS_Q, CLASSES,
                              INTRO_FIN, INTRO_REPRENDRE, INTRO_RETOUR, INTRO_SUIVANT, INTRODUCTION, ISSUE_REGLE,
                              ISSUES, LIMITE, OPERATIONS, QUESTIONNAIRE, TYPES_ORDRE, angles_du_bloc,
                              charger_reference, dollars, francais, instruments, libelle_option, nom_angle, nombre, pct)


# ---------------------------------------------------------------- les vues de l'introduction
# Chaque vue est une vraie vue du service : les chiffres viennent du moteur, sur les comptes enregistrés.

def _fiche(cid: str) -> dict:
    depart = etat.client_de_depart(cid)
    return {"id": cid, "nom": depart["nom"], "questionnaire": depart["questionnaire"],
            "portefeuille_pct": depart["portefeuille_pct"]}


def _exemple() -> tuple[dict, dict] | None:
    """Le premier compte enregistré qui a un ordre prêt, et sa fiche pour le moteur."""
    for cid, c in etat.clients().items():
        if c.get("ordre_demo"):
            return etat.client_de_depart(cid), _fiche(cid)
    return None


@st.cache_data(show_spinner=False)
def _simulation(fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    return api.simuler_ordre(fiche, ticker, sens, pourcentage)


@st.cache_data(show_spinner=False)
def _fiche_client(fiche: dict) -> dict:
    return api.lire_fiche_client(fiche)


@st.cache_data(show_spinner=False)
def _montant_compatible(fiche: dict, ticker: str, sens: str, pourcentage: float) -> float | None:
    r = api.chercher_taille_compatible(fiche, ticker, sens, pourcentage)
    return r.get("taille_compatible_pct") if isinstance(r, dict) and r.get("issue") == "compatible_avec_ajustement" \
        else None


@st.cache_data(show_spinner=False)
def _hors_politique(fiche: dict) -> bool:
    r = api.etat_des_lieux(fiche)
    return "erreur" not in r and not r.get("dans_la_politique", True)


@st.cache_data(show_spinner=False)
def _ordre_qui_rapproche(fiche: dict, essais: int = 12) -> tuple[str, float] | None:
    """Pour un portefeuille déjà hors de sa politique : un achat qui l'en rapproche, parmi les premiers titres."""
    encaisse = references.encaisse()
    for ticker in [t for t in instruments() if t != encaisse][:essais]:
        r = api.simuler_ordre(fiche, ticker, "achat", 5.0)
        if "erreur" not in r and r["direction"]["cas"] in ("hors_politique_rapproche", "revient_dans_la_politique"):
            return ticker, 5.0
    return None


def _texte_ordre(sens: str, pourcentage: float, ticker: str, valeur: float) -> str:
    return f"{str(sens).capitalize()} de {dollars(pourcentage * valeur / 100)} de {ticker}"


def _vue_cap() -> str:
    """Le cap : la zone de votre politique de placement, vos objectifs au bout, et l'écart qu'un ordre peut creuser."""
    return (f'''<svg class="cap" viewBox="0 0 520 320" role="img" aria-label="Un ordre peut garder le cap ou s'en écarter">
<rect x="16" y="150" width="444" height="64" rx="32" fill="{SAUGE}" opacity=".32"/>
<text x="40" y="140">Votre politique de placement</text>
<circle cx="476" cy="182" r="15" fill="none" stroke="{ENCRE}" stroke-width="2"/><circle cx="476" cy="182" r="5" fill="{ENCRE}"/>
<text x="476" y="226" text-anchor="middle" class="fort">Vos objectifs</text>
<path d="M40 190 C110 170 170 196 250 182" fill="none" stroke="{ENCRE}" stroke-width="3" stroke-linecap="round"/>
<path d="M250 182 C320 172 390 186 458 182" fill="none" stroke="{ENCRE}" stroke-width="2" stroke-dasharray="2 7" stroke-linecap="round"/>
<path d="M250 182 C310 160 360 110 418 62" fill="none" stroke="{OR}" stroke-width="3" stroke-linecap="round"/>
<circle cx="418" cy="62" r="6" fill="{OR}"/>
<line x1="418" y1="74" x2="418" y2="146" stroke="{GRIS}" stroke-width="1.5" stroke-dasharray="3 4"/>
<text x="428" y="112">l'écart, mesuré</text>
<circle cx="250" cy="182" r="8" fill="{ENCRE}" stroke="#fff" stroke-width="3"/>
<text x="250" y="244" text-anchor="middle" class="fort">Un ordre</text>
<text x="304" y="84" text-anchor="end">il vous en écarte</text>
<text x="356" y="202" text-anchor="middle">il garde le cap</text>
</svg>''')


def _vue_fiche() -> str:
    """Quelques réponses d'une fiche, et les limites de la politique de placement qu'elles produisent."""
    exemple = _exemple()
    if not exemple:
        return ""
    client, fiche = exemple
    fc = _fiche_client(fiche)
    if "erreur" in fc:
        return ""
    q, d = fc["questionnaire"], fc["deduit"]
    reponses = [(QUESTIONNAIRE[c]["libelle"], libelle_option(c, q[c])) for c in CHAMPS_Q[:3] if q.get(c)]
    limites = [("Profil d'investisseur", d["profil"]["libelle"])]
    for classe, zone in d["fourchettes_pct"]["valeur"].items():
        if classe == "actions":
            limites.append((CLASSES.get(classe, classe), f"{nombre(zone['min'], 0)} à {pct(zone['max'], 0)}, "
                                                         f"cible {pct(zone['cible'], 0)}"))
    try:
        pire = charger_reference("limites_risque")["pire_annee_banque_pct"]["par_profil"][d["profil"]["valeur"]]
        limites.append(("Pire année", f"{pct(abs(pire), 2)} de perte au plus"))
    except Exception:
        pass
    plafonds = d.get("plafonds_concentration_pct", {}).get("valeur")
    if plafonds:
        limites.append(("Dans une seule action", f"{pct(plafonds['action_individuelle'], 0)} au plus"))

    def liste(titre: str, paires: list) -> str:
        return (f'<div><p class="tete">{C.e(titre)}</p><dl>'
                + "".join(f"<dt>{C.e(t)}</dt><dd>{C.e(v)}</dd>" for t, v in paires) + "</dl></div>")

    fleche = (f'<svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M3 11h15M12 5l6 6-6 6" '
              f'stroke="{ENCRE}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return (f'<div class="glc-paire">{liste(f"La fiche de {client["nom"]}", reponses)}{fleche}'
            f'{liste("Sa politique de placement", limites[:4])}</div>')


def _issues() -> list[dict]:
    """Ce qu'une analyse peut apprendre, sur de vrais ordres : {qui, ordre, verdict, direction}.

    Les trois verdicts, tirés des ordres prêts des comptes enregistrés, puis le cas d'un portefeuille déjà hors
    de sa politique qu'un ordre rapproche."""
    lignes, vus = [], set()

    def ajouter(client: dict, fiche: dict, ticker: str, sens: str, pourcentage: float, hors: bool = False,
                une_fois: bool = True) -> None:
        sim = _simulation(fiche, ticker, sens, float(pourcentage))
        if "erreur" in sim or (une_fois and sim["verdict"]["code"] in vus):
            return
        vus.add(sim["verdict"]["code"])
        direction = ISSUE_REGLE if sim["verdict"]["code"] == "incompatible" else \
            ISSUES.get(sim["direction"]["cas"], sim["direction"]["libelle"])
        qui = client["nom"] + (", déjà hors de sa politique" if hors else "")
        lignes.append({"qui": qui, "ordre": _texte_ordre(sens, pourcentage, ticker, client["valeur"]),
                       "verdict": sim["verdict"], "direction": direction})

    comptes_prets = [(etat.client_de_depart(cid), _fiche(cid)) for cid, c in etat.clients().items()
                     if c.get("ordre_demo")]
    dedans = [(c, f) for c, f in comptes_prets if not _hors_politique(f)]
    for client, fiche in dedans[:1]:  # le même ordre, à un montant compatible : le verdict « compatible »
        o = client["ordre_demo"]
        compatible = _montant_compatible(fiche, o["ticker"], o["sens"], float(o["pourcentage"]))
        if compatible:
            ajouter(client, fiche, o["ticker"], o["sens"], compatible)
    for client, fiche in dedans:      # les ordres prêts : un verdict de chaque sorte
        o = client["ordre_demo"]
        ajouter(client, fiche, o["ticker"], o["sens"], o["pourcentage"])
    for client, fiche in [(c, f) for c, f in comptes_prets if _hors_politique(f)][:1]:
        rapproche = _ordre_qui_rapproche(fiche)
        if rapproche:
            ajouter(client, fiche, rapproche[0], "achat", rapproche[1], hors=True, une_fois=False)
    return lignes


def _vue_issues() -> str:
    lignes = _issues()
    if not lignes:
        return ""
    return ('<div class="glc-carte">' + "".join(
        f'<div class="glc-issue"><span class="qui">{C.e(l["qui"])} · {C.e(l["ordre"])}</span>'
        f'<span class="ou">{C.e(francais(l["direction"]))}</span>'
        f'{C.pastille(l["verdict"]["libelle"], l["verdict"]["code"])}</div>' for l in lignes) + "</div>")


def _analyse_gardee(fiche: dict, ordre: dict) -> dict | None:
    """L'analyse des agents pour cet ordre, si elle a déjà été faite et gardée : jamais d'appel aux agents ici."""
    try:
        from agent import inspection, memoire
        cle = inspection.cle_analyse(fiche, ordre["ticker"], ordre["sens"], float(ordre["pourcentage"]), "comptant",
                                     None, inspection.EQUIPE, inspection.CHEF)
        entree = memoire._trouver(cle) if cle else None
        resultat = (entree or {}).get("resultat")
        return resultat if isinstance(resultat, dict) and resultat.get("explication") else None
    except Exception:
        return None


def _vue_resultat() -> str:
    """Le résultat d'une analyse, en petit : le verdict, les angles, l'explication, les pistes testées."""
    from interface.page_negocier import paragraphes_explication
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
    tete = (f'<p style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px">'
            f'<span class="glc-sur">{C.e(client["nom"])} · '
            f'{C.e(_texte_ordre(o["sens"], o["pourcentage"], o["ticker"], client["valeur"]))}</span>'
            f'{C.pastille(sim["verdict"]["libelle"], sim["verdict"]["code"])}</p>')
    suite = ""
    gardee = _analyse_gardee(fiche, o)
    if gardee:
        # Les premières lignes de la vraie explication des agents, et les pistes qu'ils ont testées.
        for titre, texte in paragraphes_explication(gardee["explication"])[1:2]:
            suite += (f'<p class="ligne"><span>Explication · {C.e(titre)}</span>{C.e(francais(texte))}</p>')
        pistes = [p for p in gardee.get("pistes") or [] if (p.get("verdict") or {}).get("libelle")][:2]
        if pistes:
            suite += '<p class="ligne"><span>Pistes testées</span></p>' + "".join(
                f'<p class="piste"><span>{C.e(" + ".join(_texte_ordre(j.get("sens", "achat"), j.get("pourcentage", 0), j.get("ticker"), client["valeur"]) for j in p.get("ordres") or []))}</span>'
                f'{C.pastille(p["verdict"]["libelle"], p["verdict"].get("code"))}</p>' for p in pistes)
    else:
        compatible = _montant_compatible(fiche, o["ticker"], o["sens"], float(o["pourcentage"]))
        if compatible:
            suite += (f'<p class="ligne"><span>Ce qui est possible</span>Pour devenir compatible : '
                      f'{C.e(dollars(compatible * client["valeur"] / 100))} ou moins.</p>')
        suite += ('<p class="ligne"><span>Explication</span>Rédigée par deux agents, '
                  "à partir des chiffres que le code a calculés.</p>")
    return f'<div class="glc-carte glc-resume">{tete}{C.angles(lignes, LIMITE)}{suite}</div>'


def _vue_billet() -> str:
    """Le billet d'ordre d'un compte enregistré, rempli, avant le verdict."""
    exemple = _exemple()
    if not exemple:
        return ""
    client, _ = exemple
    o = client["ordre_demo"]
    instrument = instruments().get(o["ticker"], {})
    operation = OPERATIONS.get(o["sens"], {}).get("libelle", str(o["sens"]).capitalize())
    champs = [("Titre", f"{o['ticker']} — {instrument.get('nom', '')}"), ("Opération", operation),
              ("Montant", f"{dollars(o['pourcentage'] * client['valeur'] / 100)} · {pct(o['pourcentage'])} du portefeuille"),
              ("Type d'ordre", TYPES_ORDRE["marche"]["libelle"])]
    return (f'<div class="glc-carte glc-billet"><p class="glc-h2">Ordre</p><p class="glc-sur">{C.e(client["nom"])}</p>'
            + "".join(f'<div class="champ"><span>{C.e(t)}</span><b>{C.e(v)}</b></div>' for t, v in champs)
            + f'<div class="bouton">{C.e(BOUTON_ACTION)}</div></div>')


def _mots() -> dict:
    """Les mots de l'ordre prêt d'un compte enregistré, pour les titres de l'introduction qui le nomment."""
    exemple = _exemple()
    if not exemple:
        return {"nom": "Un client", "montant": "", "titre": "un titre"}
    client, _ = exemple
    o = client["ordre_demo"]
    return {"nom": client["nom"], "montant": dollars(o["pourcentage"] * client["valeur"] / 100),
            "titre": instruments().get(o["ticker"], {}).get("nom") or o["ticker"]}


VUES = {"cap": _vue_cap, "fiche": _vue_fiche, "issues": _vue_issues, "resultat": _vue_resultat,
        "billet": _vue_billet}


# ---------------------------------------------------------------- l'introduction

ASSETS = Path(__file__).resolve().parent / "assets"


@functools.lru_cache(maxsize=None)
def _clip(cle: str) -> tuple[str, str] | None:
    """Le clip d'un panneau (MP4 muet) et son affiche, encodés pour être servis avec la page elle-même :
    aucune adresse de plus à joindre, donc rien qui dépende du chemin par lequel on atteint l'application."""
    video, affiche = ASSETS / f"intro_{cle}.mp4", ASSETS / f"intro_{cle}.jpg"
    if not (video.exists() and affiche.exists()):
        return None
    return (base64.b64encode(video.read_bytes()).decode("ascii"), base64.b64encode(affiche.read_bytes()).decode("ascii"))


def vue(cle: str) -> str:
    """La vue d'un panneau : son clip s'il existe (il joue seul, muet, en boucle ; son affiche reste si la
    lecture est impossible), sinon la vue fixe, faite des vrais composants."""
    clip = _clip(cle)
    if clip is None:
        return f'<div class="glc-vue">{VUES[cle]()}</div>'
    return ('<div class="glc-vue clip"><video autoplay muted loop playsinline preload="auto" '
            f'poster="data:image/jpeg;base64,{clip[1]}" src="data:video/mp4;base64,{clip[0]}"></video></div>')


def _titre(titre: str) -> str:
    """Un titre en plusieurs phrases se lit en deux temps : les premières posent, la dernière frappe."""
    phrases = [x.strip() for x in titre.replace(". ", ".|").split("|") if x.strip()]
    if len(phrases) > 1:
        return (f'<h1><span class="avant">{C.e(" ".join(phrases[:-1]))}</span>'
                f'<span>{C.e(phrases[-1])}</span></h1>')
    return f"<h1>{C.e(titre)}</h1>"


def introduction() -> None:
    """La présentation du service en quelques panneaux : une phrase forte, une vraie vue. On la passe d'un clic."""
    dernier = len(INTRODUCTION) - 1
    n = max(0, min(dernier, st.session_state.get("intro_n", 0)))
    cle, titre, lignes, note = INTRODUCTION[n]
    if "{" in titre:
        titre = titre.format(**_mots())
    with st.container(key="introduction"):
        haut_gauche, haut_droite = st.columns([3, 1], vertical_alignment="center")
        with haut_gauche:
            points = "".join(f'<i class="{"ici" if i == n else ""}"></i>' for i in range(dernier + 1))
            C.montrer(f'<div class="glc-pas-intro"><span>{n + 1} / {dernier + 1}</span>{points}</div>')
        haut_droite.button(BOUTON_PASSER_INTRO, key="passer_intro", type="tertiary", on_click=etat.finir_introduction)
        gauche, droite = st.columns([1, 1.1], gap="large", vertical_alignment="top")
        with gauche:
            C.montrer(f'<div class="glc-intro">{_titre(titre)}' + "".join(f"<p>{C.e(l)}</p>" for l in lignes)
                      + (f'<p class="note">{C.e(note)}</p>' if note else "") + "</div>")
            retour, suivant = st.columns([1, 1.6])
            if n > 0:
                retour.button(INTRO_RETOUR, key="intro_retour", width="stretch",
                              on_click=etat.avancer_introduction, args=(-1, dernier))
            suite = INTRO_SUIVANT if n < dernier else (INTRO_REPRENDRE if st.session_state.get("compte_choisi")
                                                       else INTRO_FIN)
            suivant.button(suite, key="intro_suivant", type="primary", width="stretch",
                           on_click=etat.avancer_introduction, args=(1, dernier))
        with droite:
            C.montrer(vue(cle))


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
