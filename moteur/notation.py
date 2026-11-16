"""Notation d'un ordre (sections 7.1 à 7.6 et 8.1 de la spécification).

Échelle commune : 100 = sur la cible, 50 = exactement à la limite de la politique,
sous 50 = au-delà, plancher à 0. Chaque note renvoie ses composantes.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from . import donnees, instruments, references
from .client import poids_par_classe

SEUIL_COMPATIBLE = 50.0
PAS_TAILLE = 0.5
EPS = 1e-9


class ErreurOrdre(Exception):
    pass


# ---------------------------------------------------------------- ordre

SOURCES_OPERATIONS = {"comptant": (), "marge": ("hypothese_marge", "hypothese_levier", "hypothese_experience_operations"),
                      "decouvert": ("hypothese_decouvert", "hypothese_levier", "hypothese_experience_operations")}
OPERATIONS = {"comptant": ("achat", "vente"), "marge": ("achat",), "decouvert": ("vente",)}
LIBELLES_OPERATIONS = {"comptant": "Au comptant", "marge": "Achat sur marge", "decouvert": "Vente à découvert"}


def valider_operation(sens: str, operation: str) -> None:
    if operation not in OPERATIONS:
        raise ErreurOrdre(f"Opération invalide : « {operation} ». Choix possibles : {', '.join(OPERATIONS)}.")
    if sens in ("achat", "vente") and sens not in OPERATIONS[operation]:
        attendu = OPERATIONS[operation][0]
        raise ErreurOrdre(f"{LIBELLES_OPERATIONS[operation]} : le sens doit être « {attendu} ».")


def appliquer_ordre(port: dict, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
    """Portefeuille après l'ordre. Achat payé par l'encaisse, vente versée à l'encaisse.

    `operation` : « comptant » (par défaut), « marge » (achat qui peut dépasser l'encaisse :
    l'encaisse devient négative, c'est un emprunt) ou « decouvert » (vente au-delà du poids
    détenu : le poids de l'instrument devient négatif, le produit va à l'encaisse).
    """
    cash = references.encaisse()
    instruments.fiche(ticker)
    if sens not in ("achat", "vente"):
        raise ErreurOrdre(f"Sens invalide : « {sens} ». Choix possibles : achat, vente.")
    valider_operation(sens, operation)
    try:
        pct = float(pourcentage)
    except (TypeError, ValueError):
        raise ErreurOrdre(f"Montant invalide : « {pourcentage} ». Indiquez un pourcentage du portefeuille.")
    if not pct > 0:
        raise ErreurOrdre("Le montant de l'ordre doit être un pourcentage strictement positif du portefeuille.")
    if ticker == cash:
        raise ErreurOrdre(f"{cash} est l'encaisse du compte : un ordre sur l'encaisse elle-même n'est pas simulé.")
    nouveau = dict(port)
    if sens == "achat":
        dispo = nouveau.get(cash, 0.0)
        if operation == "comptant" and pct > dispo + EPS:
            raise ErreurOrdre(
                f"Encaisse insuffisante : l'achat de {pct:g} % dépasse l'encaisse disponible ({cash}, {dispo:g} % du portefeuille). "
                "Au comptant, l'achat ne peut pas dépasser l'encaisse : l'achat sur marge est une autre opération (« marge »)."
            )
        nouveau[cash] = dispo - pct
        nouveau[ticker] = nouveau.get(ticker, 0.0) + pct
    else:
        detenu = nouveau.get(ticker, 0.0)
        if operation == "comptant" and pct > detenu + EPS:
            raise ErreurOrdre(f"Vente impossible : le portefeuille détient {detenu:g} % de {ticker}, moins que les {pct:g} % demandés.")
        nouveau[ticker] = detenu - pct
        nouveau[cash] = nouveau.get(cash, 0.0) + pct
    return {t: w for t, w in nouveau.items() if abs(w) > EPS}


def expositions(port: dict) -> dict:
    """Exposition de chaque position en valeur absolue (concentration et thèmes).

    Une encaisse négative est un emprunt, pas une position dans le fonds de liquidités :
    elle ne compte pas comme exposition. Sans poids négatif, renvoie le portefeuille tel quel.
    """
    cash = references.encaisse()
    return {t: (max(w, 0.0) if t == cash else abs(w)) for t, w in port.items()}


def exposition_empruntee(port: dict) -> float:
    """Poids détenu à découvert ou acheté avec de l'argent emprunté : somme des poids négatifs, en valeur absolue."""
    return float(sum(-w for w in port.values() if w < 0))


def levier(port: dict) -> dict:
    """Levier = exposition brute / valeur nette. Sans emprunt ni découvert, il vaut 1."""
    brute = float(sum(expositions(port).values()))
    nette = float(sum(port.values()))
    return {"levier": brute / nette if nette > 0 else None, "exposition_brute_pct": brute, "valeur_nette_pct": nette,
            "exposition_empruntee_pct": exposition_empruntee(port)}


# ---------------------------------------------------------------- contraintes strictes

def controle_experience(fiche: dict, operation: str) -> dict | None:
    """Niveau (exclure, eviter, neutre) de l'opération avancée pour l'expérience du client.

    Lu dans `reference/operations_experience.json` (hypothèse du projet). `None` au comptant.
    """
    if operation == "comptant":
        return None
    ref = references.charger("operations_experience")
    op = ref["operations"].get(operation)
    if op is None:
        raise ErreurOrdre(f"reference/operations_experience.json : l'opération « {operation} » n'y figure pas.")
    experience = fiche["questionnaire"]["experience"]
    niveau = op["niveau_par_experience"].get(experience)
    if niveau not in ref["niveaux_permis"]:
        raise ErreurOrdre(f"reference/operations_experience.json : niveau invalide ou absent pour l'expérience « {experience} » "
                          f"({LIBELLES_OPERATIONS[operation]}). Choix possibles : {', '.join(ref['niveaux_permis'])}.")
    libelle_exp = references.charger("questionnaire")["experience"]["options"].get(experience, experience)
    return {"id": op["id"], "operation": operation, "libelle": op["libelle"], "libelle_exposition": op["libelle_exposition"],
            "experience": experience, "libelle_experience": libelle_exp, "niveau": niveau, "source": ref["source"]}


def contraintes_strictes(fiche: dict, ticker: str, sens: str, operation: str = "comptant") -> dict:
    """Section 7.1 : vérifiées pour un achat seulement. S'y ajoute l'opération avancée exclue pour l'expérience."""
    themes = {t["id"]: t for t in references.charger("themes")["themes"]}
    resultats = []
    for theme_id, reponse in fiche["questionnaire"]["themes"].items():
        if reponse not in ("exclure", "obligatoire"):
            continue
        etiquette = themes[theme_id]["etiquette"]
        valeur = instruments.valeur_etiquette(ticker, etiquette)
        if sens != "achat":
            statut, raison = "non_applicable", "Les contraintes strictes s'appliquent aux achats."
        elif valeur == "sans_objet":
            statut, raison = "ignoree", f"Le thème ne vise pas cet instrument (étiquette « {etiquette} » sans objet)."
        elif reponse == "exclure":
            if valeur is True:
                statut, raison = "violee", f"Thème exclu et étiquette « {etiquette} » vraie."
            elif valeur == "indetermine":
                statut, raison = "signalee", f"Étiquette « {etiquette} » indéterminée : non violée, mais à signaler."
            else:
                statut, raison = "respectee", f"Étiquette « {etiquette} » fausse."
        else:  # obligatoire
            if valeur is True:
                statut, raison = "respectee", f"Étiquette « {etiquette} » vraie."
            elif valeur == "indetermine":
                statut, raison = "violee", f"Étiquette « {etiquette} » indéterminée : la condition obligatoire n'est pas démontrée."
            else:
                statut, raison = "violee", f"Thème obligatoire et étiquette « {etiquette} » fausse."
        detail = instruments.fiche(ticker)["etiquettes"].get(etiquette, {})
        resultats.append({"theme": theme_id, "reponse": reponse, "etiquette": etiquette, "valeur_etiquette": valeur,
                          "statut": statut, "raison": raison, "declencheur": detail.get("declencheur"),
                          "source": detail.get("source")})
    ce = controle_experience(fiche, operation)
    if ce and ce["niveau"] == "exclure":
        resultats.append({"theme": ce["id"], "reponse": "exclure", "etiquette": None, "valeur_etiquette": None,
                          "statut": "violee", "controle": "experience_operation",
                          "raison": f"{ce['libelle']} exclu pour l'expérience « {ce['libelle_experience']} » (hypothèse du projet).",
                          "declencheur": f"experience = {ce['experience']}", "source": ce["source"]})
    violees = [r["theme"] for r in resultats if r["statut"] == "violee"]
    return {"violee": bool(violees), "themes_violes": violees, "detail": resultats}


# ---------------------------------------------------------------- risque

def _poids_etalon(fractions_classes: dict) -> dict:
    etalons = references.charger("portefeuilles_etalons")["etalons_par_classe"]
    poids = {}
    for classe, part in fractions_classes.items():
        for t, w in etalons[classe].items():
            poids[t] = poids.get(t, 0.0) + part * w
    return poids


@lru_cache(maxsize=32)
def _baisses_etalons(profil_id: str, dossier: str) -> dict:
    f = references.charger("profils")["profils"][profil_id]["fourchettes"]
    reference = {c: v["cible"] for c, v in f.items()}
    limite = {c: 0.0 for c in f}
    limite["actions"] = f["actions"]["max"]
    limite["revenu_fixe"] = 100.0 - f["actions"]["max"]
    s_ref = donnees.statistiques(_poids_etalon(reference))
    s_lim = donnees.statistiques(_poids_etalon(limite))
    return {"reference": {"composition_pct": reference, **s_ref}, "limite": {"composition_pct": limite, **s_lim}}


def baisses_etalons(profil_id: str) -> dict:
    return _baisses_etalons(profil_id, str(donnees.dossier_donnees()))


def note_ampleur(d: float, d_ref: float, d_lim: float) -> float:
    if d <= d_ref:
        return 100.0
    if d <= d_lim:
        return 100.0 - 50.0 * (d - d_ref) / (d_lim - d_ref)
    return max(0.0, 50.0 - 50.0 * (d - d_lim) / d_lim)


def note_duree(t: float, h: float) -> float:
    if h <= 0:
        return 100.0 if t <= 0 else 0.0
    return max(0.0, 100.0 - 50.0 * t / h)


def volatilite_mensuelle(valeur) -> float | None:
    """Écart-type des rendements mensuels (fin de mois), annualisé par racine(12), comme l'Annexe F du Règlement 81-102."""
    r = valeur.resample("ME").last().pct_change().dropna()
    if len(r) < 12:
        return None
    return float(r.std(ddof=1) * np.sqrt(12))


def mesure_fluctuations(valeur, profil_id: str) -> dict:
    ref = references.charger("limites_risque")["bandes_volatilite_pct"]
    b = ref["par_profil"][profil_id]
    vol = volatilite_mensuelle(valeur)
    m = {"libelle": "Fluctuations : écart-type annualisé des rendements mensuels, face à l'échelle des régulateurs",
         "niveau": b["niveau"], "cible": b["min"] / 100.0, "limite": None if b["max"] is None else b["max"] / 100.0,
         "valeur": vol, "unite": "fraction", "source": ref["source"], "hypothese": "hypothese_risque_familles"}
    if b["max"] is None:
        m.update(note=None, statut="sans_objet",
                 phrase=f"{_fr(vol * 100)} % ; niveau « {b['niveau']} » sans plafond publié" if vol is not None else "")
    elif vol is None:
        m.update(note=None, statut="indetermine")
    else:
        m.update(note=note_lineaire(vol, b["min"] / 100.0, b["max"] / 100.0),
                 phrase=f"{_fr(vol * 100)} % par an ; niveau « {b['niveau']} » : {b['min']} à {b['max']} %")
    return m


def mesure_pire_annee(valeur, profil_id: str) -> dict:
    limite, src = _pire_annee_banque(profil_id)
    pf = pire_fenetre(valeur, 1)
    m = {"libelle": "Pire année : pire rendement sur douze mois glissants", "cible": 0.0, "limite": limite,
         "unite": "fraction", "source": src, "hypothese": "hypothese_risque_familles"}
    if pf["valeur"] is None:
        m.update(note=None, statut="indetermine")
    else:
        m.update(note=note_lineaire(pf["valeur"], 0.0, limite), valeur=pf["valeur"], debut=pf["debut"], fin=pf["fin"],
                 phrase=f"{_fr(pf['valeur'] * 100)} % ; pire année publiée pour le profil : {_fr(limite * 100, 2)} %")
    return m


def note_risque(port: dict, fiche: dict) -> dict:
    stats = donnees.statistiques(port)
    profil_id = fiche["deduit"]["profil"]["valeur"]
    et = baisses_etalons(profil_id)
    d = abs(stats["pire_baisse"])
    d_ref = abs(et["reference"]["pire_baisse"])
    d_lim = abs(et["limite"]["pire_baisse"])
    h = fiche["deduit"]["horizon_annees"]["valeur"]
    t = stats["temps_sous_l_eau_annees"]
    ampleur = note_ampleur(d, d_ref, d_lim)
    duree = note_duree(t, h)
    mesures = {
        "ampleur": {"note": ampleur, "pire_baisse": -d, "pire_baisse_reference": -d_ref, "pire_baisse_limite": -d_lim,
                    "libelle": "Ampleur de la pire baisse, comparée aux portefeuilles étalons du profil"},
        "duree": {"note": duree, "temps_sous_l_eau_annees": t, "horizon_annees": h,
                  "non_recupere": stats["non_recupere"], "debut": stats["temps_sous_l_eau_debut"],
                  "fin": stats["temps_sous_l_eau_fin"],
                  "libelle": "Durée sous l'eau, comparée à l'horizon"},
    }
    valeur = donnees.valeur_portefeuille(port)
    mesures["fluctuations"] = mesure_fluctuations(valeur, profil_id)
    mesures["pire_annee"] = mesure_pire_annee(valeur, profil_id)
    famille = _noter(mesures)
    return {**famille,
            "volatilite_annualisee": stats["volatilite_annualisee"],
            "etalons": {"reference": et["reference"]["composition_pct"], "limite": et["limite"]["composition_pct"]}}


# ---------------------------------------------------------------- diversification

def note_classe(w: float, b: float, c: float, h: float) -> float:
    if w > c:
        n = 100.0 - 50.0 * (w - c) / (h - c) if h > c else 0.0
    elif w < c:
        n = 100.0 - 50.0 * (c - w) / (c - b) if c > b else 0.0
    else:
        n = 100.0
    return max(0.0, n)


def _plafond(w: float, plafond: float) -> float:
    return max(0.0, 100.0 - 50.0 * w / plafond)


def note_diversification(port: dict, fiche: dict) -> dict:
    fourchettes = fiche["deduit"]["fourchettes_pct"]["valeur"]
    plafonds = fiche["deduit"]["plafonds_concentration_pct"]["valeur"]
    crypto = fiche["deduit"]["crypto_pct"]["valeur"]
    classes = poids_par_classe(port)
    ex = expositions(port)
    mesures = {}
    for c, f in fourchettes.items():
        w = classes.get(c, 0.0)
        mesures[f"classe_{c}"] = {"note": note_classe(w, f["min"], f["cible"], f["max"]), "poids": w,
                                  "min": f["min"], "cible": f["cible"], "max": f["max"],
                                  "libelle": f"Poids de la classe « {c} » face à sa fourchette"}
    w_crypto = sum(w for t, w in ex.items() if instruments.fiche(t)["classe_actif"] == "crypto")
    mesures["crypto"] = {"note": _plafond(w_crypto, crypto["plafond_pct"]), "poids": w_crypto,
                         "plafond": crypto["plafond_pct"], "libelle": "Poids des cryptoactifs face au plafond du profil"}

    actions = {t: w for t, w in ex.items() if w > EPS and instruments.est_action_individuelle(t)}
    fonds = {t: w for t, w in ex.items() if w > EPS and instruments.est_fonds(t)}
    if actions:
        t_max = max(actions, key=actions.get)
        mesures["plus_grosse_action"] = {"note": _plafond(actions[t_max], plafonds["action_individuelle"]),
                                         "ticker": t_max, "poids": actions[t_max], "plafond": plafonds["action_individuelle"],
                                         "libelle": "Plus grosse action individuelle"}
        secteurs: dict[str, float] = {}
        for t, w in actions.items():
            s = instruments.fiche(t)["secteur"]
            secteurs[s] = secteurs.get(s, 0.0) + w
        s_max = max(secteurs, key=secteurs.get)
        mesures["plus_gros_secteur"] = {"note": _plafond(secteurs[s_max], plafonds["secteur"]), "secteur": s_max,
                                        "poids": secteurs[s_max], "plafond": plafonds["secteur"],
                                        "libelle": "Plus gros secteur (actions individuelles)"}
    else:
        mesures["plus_grosse_action"] = {"note": 100.0, "ticker": None, "poids": 0.0, "plafond": plafonds["action_individuelle"],
                                         "libelle": "Plus grosse action individuelle"}
        mesures["plus_gros_secteur"] = {"note": 100.0, "secteur": None, "poids": 0.0, "plafond": plafonds["secteur"],
                                        "libelle": "Plus gros secteur (actions individuelles)"}
    if fonds:
        f_max = max(fonds, key=fonds.get)
        mesures["plus_gros_fonds"] = {"note": _plafond(fonds[f_max], plafonds["fonds_negocie_en_bourse"]), "ticker": f_max,
                                      "poids": fonds[f_max], "plafond": plafonds["fonds_negocie_en_bourse"],
                                      "libelle": "Plus gros fonds négocié en bourse"}
    else:
        mesures["plus_gros_fonds"] = {"note": 100.0, "ticker": None, "poids": 0.0,
                                      "plafond": plafonds["fonds_negocie_en_bourse"], "libelle": "Plus gros fonds négocié en bourse"}
    mesures["geographie_actions"] = mesure_geographie(ex)
    return {**_noter(mesures), "poids_par_classe": classes}


def mesure_geographie(ex: dict) -> dict:
    """Part des actions canadiennes dans les actions, face à la répartition de référence de la banque."""
    g = references.charger("limites_risque")["geographie_actions"]
    actions = {t: w for t, w in ex.items() if w > EPS and references.classe_politique(t) == "actions"}
    total = sum(actions.values())
    m = {"libelle": "Part des actions canadiennes dans les actions", "cible": g["cible_canada_pct"],
         "limite_basse": g["cible_canada_pct"] - g["ecart_limite_points"],
         "limite_haute": g["cible_canada_pct"] + g["ecart_limite_points"], "unite": "%",
         "source": g["source_cible"], "source_limite": g["source_ecart"], "hypothese": "hypothese_geographie"}
    if total <= EPS:
        m.update(note=None, statut="sans_objet", phrase="aucune action")
        return m
    canada = sum(w for t, w in actions.items() if instruments.fiche(t)["devise"] == "CAD") / total * 100
    m.update(valeur=canada, hors_canada=100 - canada,
             note=note_lineaire(abs(canada - g["cible_canada_pct"]), 0.0, float(g["ecart_limite_points"])),
             phrase=f"Canada {_fr(canada, 0)} % des actions, ailleurs {_fr(100 - canada, 0)} % ; "
                    f"référence 40 / 60, limite {m['limite_basse']} à {m['limite_haute']} % au Canada")
    return m


# ---------------------------------------------------------------- préférences souples

def note_preferences(port: dict, fiche: dict, ordre: dict | None = None) -> dict:
    themes = {t["id"]: t for t in references.charger("themes")["themes"]}
    repere = references.charger("themes")["repere_preferences_souples_pct"]
    mesures = {}
    signalements = []
    for theme_id, reponse in fiche["questionnaire"]["themes"].items():
        if reponse not in ("eviter", "rechercher"):
            continue
        etiquette = themes[theme_id]["etiquette"]
        if reponse == "eviter":
            portes = {t: w for t, w in expositions(port).items() if instruments.valeur_etiquette(t, etiquette) is True}
            indet = [t for t in port if instruments.valeur_etiquette(t, etiquette) == "indetermine"]
            e = sum(portes.values())
            mesures[theme_id] = {"note": max(0.0, 100.0 - 50.0 * e / repere), "reponse": reponse, "poids_expose": e,
                                 "instruments": portes, "etiquette_indeterminee": indet,
                                 "libelle": f"Poids du portefeuille dans le thème évité « {theme_id} »"}
        else:
            note, vendu = 100.0, 0.0
            if ordre and instruments.valeur_etiquette(ordre["ticker"], etiquette) is True:
                if ordre["sens"] == "vente":
                    vendu = float(ordre["pourcentage"])
                    note = max(0.0, 100.0 - 50.0 * vendu / repere)
                else:
                    signalements.append({"theme": theme_id, "message": f"Achat dans le thème recherché « {theme_id} » : favorable à la préférence."})
            mesures[theme_id] = {"note": note, "reponse": reponse, "poids_vendu": vendu,
                                 "libelle": f"Thème recherché « {theme_id} »"}
    ce = controle_experience(fiche, ordre.get("operation", "comptant")) if ordre else None
    if ce and ce["niveau"] == "eviter":
        e = exposition_empruntee(port)
        mesures[ce["id"]] = {"note": max(0.0, 100.0 - 50.0 * e / repere), "reponse": "eviter", "poids_expose": e,
                             "operation": ce["operation"], "experience": ce["experience"], "source": ce["source"],
                             "libelle": f"{ce['libelle_exposition']} ({ce['libelle'].lower()}, "
                                        f"expérience « {ce['libelle_experience']} »)"}
    if not mesures:
        return {"note": 100.0, "mesure_min": None, "sans_objet": True, "mesures": {}, "signalements": [],
                "libelle": "Aucune préférence souple : sans objet."}
    mesure_min = min(mesures, key=lambda k: mesures[k]["note"])
    return {"note": mesures[mesure_min]["note"], "mesure_min": mesure_min, "sans_objet": False, "mesures": mesures,
            "signalements": signalements}


# ---------------------------------------------------------------- échelle commune et familles

def _fr(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def note_lineaire(x: float, cible: float, limite: float) -> float:
    """Échelle commune : 100 sur la cible, 50 à la limite, droite prolongée au-delà ; plancher 0, plafond 100."""
    if limite == cible:
        return 100.0 if x == cible else 0.0
    return float(min(100.0, max(0.0, 100.0 - 50.0 * (x - cible) / (limite - cible))))


def _noter(mesures: dict) -> dict:
    """Note d'une famille : sa mesure la plus faible ; une mesure sans note (indetermine, sans_objet) ne décide pas."""
    notees = {k: m for k, m in mesures.items() if isinstance(m.get("note"), (int, float))}
    if not notees:
        return {"note": None, "mesure_min": None, "sans_objet": True, "mesures": mesures}
    mesure_min = min(notees, key=lambda k: notees[k]["note"])
    return {"note": notees[mesure_min]["note"], "mesure_min": mesure_min, "mesures": mesures}


FAMILLES = {
    "objectif": "L'ordre sert-il mon objectif ?",
    "risque": "Le risque reste-t-il dans ce que j'accepte ?",
    "liquidite": "Mon argent reste-t-il disponible ?",
    "diversification": "Mon portefeuille reste-t-il bien réparti ?",
    "preferences": "L'ordre respecte-t-il mes préférences ?",
}
FENETRE_MIN_ANNEES, FENETRE_MAX_ANNEES = 1, 3


def pire_fenetre(valeur, annees: float) -> dict:
    """Pire rendement cumulé sur une fenêtre glissante de `annees` ans (en séances du calendrier, 252 par an)."""
    n = int(round(annees * donnees.JOURS_PAR_AN))
    v = valeur.to_numpy()
    if len(v) <= n:
        return {"valeur": None}
    r = v[n:] / v[:-n] - 1.0
    i = int(np.argmin(r))
    return {"valeur": float(r[i]), "debut": valeur.index[i].date().isoformat(),
            "fin": valeur.index[i + n].date().isoformat()}


def _pire_annee_banque(profil_id: str) -> tuple[float, str]:
    ref = references.charger("limites_risque")["pire_annee_banque_pct"]
    return ref["par_profil"][profil_id] / 100.0, ref["source"]


def _rendement_revenu(poids_pct: dict) -> float | None:
    total = 0.0
    for t, w in poids_pct.items():
        y = ((instruments.fiche(t).get("faits_marche") or {}).get("revenu") or {}).get("rendement_dividende")
        if not isinstance(y, (int, float)):
            return None
        total += w / 100.0 * y
    return total


def note_objectif(port: dict, fiche: dict) -> dict:
    obj = fiche["questionnaire"]["objectif"]
    profil_id = fiche["deduit"]["profil"]["valeur"]
    f_actions = fiche["deduit"]["fourchettes_pct"]["valeur"]["actions"]
    base = {"objectif": obj, "source": "hypothese_objectif"}
    if obj == "preserver_capital":
        h = float(fiche["deduit"]["horizon_annees"]["valeur"])
        annees = min(FENETRE_MAX_ANNEES, max(FENETRE_MIN_ANNEES, h))
        pf = pire_fenetre(donnees.valeur_portefeuille(port), annees)
        pente, src = _pire_annee_banque(profil_id)
        m = {**base, "libelle": "Pire rendement cumulé sur une fenêtre de la durée de l'horizon",
             "fenetre_annees": annees, "horizon_annees": h, "fenetre_ajustee": annees != h,
             "cible": abs(pente), "limite": 0.0, "unite": "fraction", "source_pente": src}
        if pf["valeur"] is None:
            m.update(note=None, statut="indetermine")
        else:
            m.update(note=note_lineaire(pf["valeur"], abs(pente), 0.0), valeur=pf["valeur"],
                     debut=pf["debut"], fin=pf["fin"],
                     phrase=f"pire rendement sur {_fr(annees, 0)} an(s) : {_fr(pf['valeur'] * 100)} % ; limite : 0 % (capital intact)")
        return _noter({"capital_preserve": m})
    if obj == "revenu_regulier":
        et = baisses_etalons(profil_id)
        y = _rendement_revenu(port)
        cible = _rendement_revenu(_poids_etalon(et["reference"]["composition_pct"]))
        limite = _rendement_revenu(_poids_etalon(et["limite"]["composition_pct"]))
        m = {**base, "libelle": "Rendement en revenu du portefeuille (dividendes des 12 derniers mois)",
             "unite": "fraction", "source_donnees": "donnees_dividendes"}
        if y is None or cible is None or limite is None:
            m.update(note=None, statut="indetermine")
            return _noter({"revenu": m})
        moitie = limite >= cible
        if moitie:
            limite = cible / 2.0
        m.update(note=note_lineaire(y, cible, limite), valeur=y, cible=cible, limite=limite,
                 limite_moitie_de_la_cible=moitie,
                 phrase=f"revenu {_fr(y * 100, 2)} % par an ; cible {_fr(cible * 100, 2)} %, limite {_fr(limite * 100, 2)} %")
        return _noter({"revenu": m})
    w = poids_par_classe(port).get("actions", 0.0)
    b, c, hmax = f_actions["min"], f_actions["cible"], f_actions["max"]
    if obj == "croissance_equilibree":
        note = note_classe(w, b, c, hmax)
        phrase = f"actions {_fr(w)} % ; cible {_fr(c, 0)} %, permis {_fr(b, 0)} à {_fr(hmax, 0)} %"
    else:  # croissance_long_terme : côté bas seulement
        note = 100.0 if w >= c else note_lineaire(w, c, b)
        phrase = f"actions {_fr(w)} % ; cible {_fr(c, 0)} % ou plus, minimum {_fr(b, 0)} %"
    return _noter({"actions": {**base, "libelle": "Poids des actions face à la fourchette du profil", "note": note,
                               "valeur": w, "cible": c, "limite": b, "max": hmax, "unite": "%", "phrase": phrase}})


def note_liquidite(port: dict, fiche: dict) -> dict:
    """Liquidités gardées face au besoin de l'année : limite (50) = le besoin, cible (100) = besoin + cible du profil."""
    besoin = float(fiche["deduit"].get("besoin_liquidite_pct", {}).get("valeur", 0) or 0)
    if not besoin:
        return {"note": None, "mesure_min": None, "sans_objet": True, "mesures": {},
                "libelle": "Aucun besoin de liquidités déclaré : sans objet."}
    cible_profil = fiche["deduit"]["fourchettes_pct"]["valeur"]["liquidites"]["cible"]
    cash = float(port.get(references.encaisse(), 0.0))
    cible, limite = besoin + cible_profil, besoin
    return _noter({"liquidites_besoin": {
        "libelle": "Liquidités gardées face au besoin de l'année", "note": note_lineaire(cash, cible, limite),
        "valeur": cash, "cible": cible, "limite": limite, "besoin": besoin, "unite": "%",
        "source": "hypothese_besoin_liquidite",
        "phrase": f"liquidités {_fr(cash)} % ; besoin {_fr(besoin, 0)} %, cible {_fr(cible, 0)} %"}})


# ---------------------------------------------------------------- score

def evaluer(port: dict, fiche: dict, ordre: dict | None = None) -> dict:
    notes = {
        "objectif": note_objectif(port, fiche),
        "risque": note_risque(port, fiche),
        "liquidite": note_liquidite(port, fiche),
        "diversification": note_diversification(port, fiche),
        "preferences": note_preferences(port, fiche, ordre),
    }
    for fam, n in notes.items():
        n["question"] = FAMILLES[fam]
    notees = {k: n for k, n in notes.items() if isinstance(n.get("note"), (int, float))}
    dim = min(notees, key=lambda k: notees[k]["note"])
    score = notees[dim]["note"]
    return {"score": score, "dimension_min": dim, "mesure_min": notes[dim]["mesure_min"], "notes": notes,
            "familles": list(notes), "dans_la_politique": score >= SEUIL_COMPATIBLE}


def direction(score_avant: float, score_apres: float) -> dict:
    if score_avant >= SEUIL_COMPATIBLE:
        if score_apres >= SEUIL_COMPATIBLE:
            cas, lib = "reste_dans_la_politique", "Reste dans la politique"
        else:
            cas, lib = "fait_sortir_de_la_politique", "Fait sortir de la politique"
    elif score_apres > score_avant:
        cas, lib = "hors_politique_rapproche", "Hors politique et rapproche"
    else:
        cas, lib = "hors_politique_aggrave", "Hors politique et aggrave"
    return {"cas": cas, "libelle": lib, "score_avant": score_avant, "score_apres": score_apres,
            "revient_dans_la_politique": score_avant < SEUIL_COMPATIBLE <= score_apres}


def contribution_risque(port: dict, ticker: str) -> dict:
    """Part du risque total (variance) qui vient d'un titre : w_i x cov(r_i, r_p) / var(r_p)."""
    total = sum(port.values())
    w = {t: v / total for t, v in port.items()}
    rend = donnees.rendements_cad()[list(w)].fillna(0.0)
    rp = rend.to_numpy() @ np.array(list(w.values()))
    var_p = float(np.var(rp, ddof=1))
    if ticker not in w or var_p <= 0:
        return {"ticker": ticker, "poids_pct": 0.0, "part_du_risque_pct": 0.0}
    cov = float(np.cov(rend[ticker].to_numpy(), rp, ddof=1)[0, 1])
    return {"ticker": ticker, "poids_pct": w[ticker] * 100.0, "part_du_risque_pct": w[ticker] * cov / var_p * 100.0}


def verdict(contraintes: dict, score: float) -> dict:
    if contraintes["violee"]:
        return {"code": "incompatible", "libelle": "Incompatible",
                "raison": "Contrainte stricte violée : " + ", ".join(contraintes["themes_violes"]) + "."}
    if score >= SEUIL_COMPATIBLE:
        return {"code": "compatible", "libelle": "Compatible", "raison": "Score de 50 ou plus."}
    return {"code": "en_tension", "libelle": "En tension", "raison": "Score sous 50 : au-delà d'une limite de la politique."}


def bloc_operation(port_avant: dict, port_apres: dict, operation: str, fiche: dict, apres: dict) -> dict:
    """Type d'opération, levier avant et après (affiché, non noté), hypothèses et limites."""
    lv_avant, lv_apres = levier(port_avant), levier(port_apres)
    bloc = {"code": operation, "libelle": LIBELLES_OPERATIONS[operation],
            "levier_avant": lv_avant["levier"], "levier_apres": lv_apres["levier"],
            "exposition_brute_apres_pct": lv_apres["exposition_brute_pct"],
            "exposition_empruntee_apres_pct": lv_apres["exposition_empruntee_pct"],
            "hypotheses": [], "limites": []}
    if operation != "comptant":
        for s in references.sources(*SOURCES_OPERATIONS[operation]):
            bloc["hypotheses"].append({"id": s["id"], "libelle": s["libelle"]})
            if s.get("limite"):
                bloc["limites"].append(s["limite"])
    ce = controle_experience(fiche, operation)
    if ce is None:
        bloc["controle_experience"] = {"effet": "aucun", "raison": "Opération au comptant."}
    else:
        controle = {"id": ce["id"], "experience": ce["experience"], "niveau": ce["niveau"], "source": ce["source"]}
        if ce["niveau"] == "exclure":
            controle.update(effet="contrainte_stricte", statut="violee",
                            raison=f"{ce['libelle']} exclu pour l'expérience « {ce['libelle_experience']} ».")
        elif ce["niveau"] == "eviter":
            m = apres["notes"]["preferences"]["mesures"][ce["id"]]
            controle.update(effet="preference_souple", note=m["note"], poids_expose=m["poids_expose"],
                            raison=f"{ce['libelle']} à éviter pour l'expérience « {ce['libelle_experience']} ».")
        else:
            controle.update(effet="aucun", raison=f"{ce['libelle']} sans effet pour l'expérience « {ce['libelle_experience']} ».")
        bloc["controle_experience"] = controle
    return bloc


def simuler(fiche: dict, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
    port_avant = fiche["portefeuille_pct"]
    port_apres = appliquer_ordre(port_avant, ticker, sens, pourcentage, operation)
    ordre = {"ticker": ticker, "sens": sens, "pourcentage": float(pourcentage), "operation": operation}
    cs = contraintes_strictes(fiche, ticker, sens, operation)
    avant = evaluer(port_avant, fiche)
    apres = evaluer(port_apres, fiche, ordre)
    dirn = direction(avant["score"], apres["score"])
    if cs["violee"]:
        dirn["remarque"] = "Direction lue sur les notes seulement : une contrainte stricte est violée, l'ordre est incompatible."
    resultat = {
        "ordre": ordre,
        "portefeuille_avant_pct": port_avant,
        "portefeuille_apres_pct": port_apres,
        "contraintes_strictes": cs,
        "avant": avant,
        "apres": apres,
        "verdict": verdict(cs, apres["score"]),
        "direction": dirn,
        "contribution_risque_apres": contribution_risque(port_apres, ticker),
        "operation": bloc_operation(port_avant, port_apres, operation, fiche, apres),
        "cause": cause(fiche, [ordre], cs, apres, port_apres),
    }
    resultat["points_attention"] = points_attention(fiche, resultat["operation"])
    return resultat


def taille_compatible(fiche: dict, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
    """Plus grande taille, par pas de 0,5 %, jusqu'au montant demandé, avec score >= 50."""
    port = fiche["portefeuille_pct"]
    appliquer_ordre(port, ticker, sens, pourcentage, operation)  # valide l'ordre demandé
    cs = contraintes_strictes(fiche, ticker, sens, operation)
    if cs["violee"]:
        return {"lancee": False, "taille_compatible_pct": None, "courbe": [], "contraintes_strictes": cs,
                "raison": "Contrainte stricte violée : aucune taille ne réparerait la violation."}
    n = int(np.floor(float(pourcentage) / PAS_TAILLE + 1e-9))
    tailles = [round(PAS_TAILLE * k, 4) for k in range(1, n + 1)]
    if not tailles or abs(tailles[-1] - float(pourcentage)) > 1e-9:
        tailles.append(float(pourcentage))
    courbe = []
    for x in tailles:
        port_x = appliquer_ordre(port, ticker, sens, x, operation)
        ev = evaluer(port_x, fiche, {"ticker": ticker, "sens": sens, "pourcentage": x, "operation": operation})
        point = {"taille_pct": x, "score": ev["score"], "dimension_min": ev["dimension_min"], "mesure_min": ev["mesure_min"]}
        if operation != "comptant":
            point["levier"] = levier(port_x)["levier"]
        courbe.append(point)
    ok = [p["taille_pct"] for p in courbe if p["score"] >= SEUIL_COMPATIBLE]
    taille = max(ok) if ok else None
    if taille is None:
        issue = "aucune_taille"
    elif abs(taille - float(pourcentage)) < 1e-9:
        issue = "compatible_tel_quel"
    else:
        issue = "compatible_avec_ajustement"
    return {"lancee": True, "taille_compatible_pct": taille, "taille_demandee_pct": float(pourcentage), "issue": issue,
            "pas_pct": PAS_TAILLE, "courbe": courbe, "contraintes_strictes": cs}


# ---------------------------------------------------------------- cause du verdict

PLAFONDS = ("plus_grosse_action", "plus_gros_fonds", "plus_gros_secteur", "crypto")


def cause(fiche: dict, ordres: list, cs: dict, apres: dict, port_apres: dict) -> dict:
    """Ce qui décide du verdict, lu dans les notes déjà calculées : aucune note nouvelle.

    `type` : `contrainte_stricte`, `risque`, `classe`, `plafond` ou `preference`, avec ce qui fait la mesure
    (l'instrument et son poids pour un plafond, la classe et sa fourchette, le thème et son exposition, la mesure
    de risque et sa limite). `porte_par_l_ordre` dit si un instrument de l'ordre est en cause.
    """
    tickers = [o["ticker"] for o in ordres]
    if cs["violee"]:
        return {"type": "contrainte_stricte", "themes_violes": cs["themes_violes"], "sous_le_seuil": True,
                "libelle": "Une contrainte stricte est violée : le verdict vient d'elle seule."}
    dim, mes = apres["dimension_min"], apres["mesure_min"]
    m = apres["notes"][dim]["mesures"].get(mes, {}) if mes else {}
    c = {"dimension": dim, "mesure": mes, "note": apres["score"], "sous_le_seuil": apres["score"] < SEUIL_COMPATIBLE,
         # La mesure telle que le moteur la décrit (entrées, cible, limite, source…), quelle que soit sa famille.
         "detail_mesure": {k: v for k, v in m.items() if not isinstance(v, (list, dict)) or k in
                           ("entrees", "cible", "limite", "source", "sources")}}
    if dim == "risque" and mes not in ("ampleur", "duree") or dim in ("objectif", "liquidite"):
        c.update(type=dim, valeur=m.get("valeur"), cible=m.get("cible"), limite=m.get("limite"),
                 libelle_mesure=m.get("libelle"), phrase=m.get("phrase"))
        c["porte_par_l_ordre"] = True
        if dim == "risque":
            c["part_du_risque_pct"] = {t: contribution_risque(port_apres, t)["part_du_risque_pct"] for t in tickers
                                       if t in port_apres}
    elif dim == "risque":
        c["type"] = "risque"
        if mes == "ampleur":
            c.update(valeur=m.get("pire_baisse"), limite=m.get("pire_baisse_limite"),
                     reference=m.get("pire_baisse_reference"))
        else:
            c.update(valeur=m.get("temps_sous_l_eau_annees"), limite=m.get("horizon_annees"),
                     non_recupere=m.get("non_recupere"))
        c["part_du_risque_pct"] = {t: contribution_risque(port_apres, t)["part_du_risque_pct"] for t in tickers
                                   if t in port_apres}
        c["porte_par_l_ordre"] = any(o["sens"] == "achat" for o in ordres)
    elif mes and mes.startswith("classe_"):
        classe = mes[len("classe_"):]
        c.update(type="classe", classe=classe, poids=m.get("poids"), min=m.get("min"), cible=m.get("cible"),
                 max=m.get("max"), cote="au_dessus" if m.get("poids", 0) > m.get("cible", 0) else "en_dessous",
                 classes_des_ordres={t: instruments.fiche(t)["classe_politique"] for t in tickers})
        c["porte_par_l_ordre"] = classe in c["classes_des_ordres"].values()
    elif mes in PLAFONDS:
        c.update(type="plafond", poids=m.get("poids"), plafond=m.get("plafond"))
        if mes == "plus_gros_secteur":
            c["secteur"] = m.get("secteur")
            c["porte_par_l_ordre"] = any(instruments.fiche(t)["secteur"] == m.get("secteur")
                                         and instruments.est_action_individuelle(t) for t in tickers)
        elif mes == "crypto":
            c["porte_par_l_ordre"] = any(instruments.fiche(t)["classe_actif"] == "crypto" for t in tickers)
        else:
            c["instrument"] = m.get("ticker")
            c["porte_par_l_ordre"] = m.get("ticker") in tickers
    elif dim == "preferences":
        c.update(type="preference", theme=mes, reponse=m.get("reponse"), poids_expose=m.get("poids_expose"),
                 instruments=m.get("instruments") or {})
        c["porte_par_l_ordre"] = any(t in (m.get("instruments") or {}) for t in tickers) or bool(m.get("operation"))
    else:
        # Une famille que ce code ne connaît pas : la mesure se lit dans `detail_mesure`.
        c["type"] = dim
    c["autres_mesures_sous_le_seuil"] = [
        {"dimension": d, "mesure": k, "note": v["note"]}
        for d, n in apres["notes"].items() for k, v in n["mesures"].items()
        if isinstance(v.get("note"), (int, float)) and v["note"] < SEUIL_COMPATIBLE and (d, k) != (dim, mes)]
    return c


# ---------------------------------------------------------------- scénario de plusieurs ordres

MAX_ORDRES_SCENARIO = 4


def _jambes(ordres) -> list:
    if not isinstance(ordres, (list, tuple)) or not 1 <= len(ordres) <= MAX_ORDRES_SCENARIO:
        raise ErreurOrdre(f"Un scénario compte de 1 à {MAX_ORDRES_SCENARIO} ordres.")
    jambes = []
    for o in ordres:
        if not isinstance(o, dict):
            raise ErreurOrdre("Chaque ordre du scénario est un objet {ticker, sens, pourcentage}.")
        try:
            pct = float(o.get("pourcentage"))
        except (TypeError, ValueError):
            raise ErreurOrdre(f"Montant invalide : « {o.get('pourcentage')} ». Indiquez un pourcentage du portefeuille.")
        jambes.append({"ticker": str(o.get("ticker", "")).strip().upper(), "sens": str(o.get("sens", "")).strip().lower(),
                       "pourcentage": pct, "operation": str(o.get("operation") or "comptant").strip().lower()})
    tickers = [j["ticker"] for j in jambes]
    if len(set(tickers)) != len(tickers):
        raise ErreurOrdre("Un même instrument apparaît deux fois dans le scénario : regroupez ces ordres.")
    achats = sum(j["pourcentage"] for j in jambes if j["sens"] == "achat")
    ventes = sum(j["pourcentage"] for j in jambes if j["sens"] == "vente")
    if achats > EPS and ventes > achats + EPS:
        raise ErreurOrdre(f"Dans un scénario, les ventes servent à payer les achats : leur total ({ventes:g} %) ne peut "
                          f"pas dépasser celui des achats ({achats:g} %).")
    return jambes


def simuler_scenario(fiche: dict, ordres: list) -> dict:
    """Plusieurs ordres appliqués ensemble (ventes d'abord, versées à l'encaisse ; achats payés par l'encaisse).

    Même forme que `simuler`, plus `ordres`. Notes, verdict et direction viennent des formules de `simuler` ;
    chaque ordre passe sa propre opération et son propre thème à la note de préférences, et la plus basse est gardée.
    """
    jambes = _jambes(ordres)
    port_avant = fiche["portefeuille_pct"]
    port_apres = port_avant
    for j in sorted(jambes, key=lambda j: j["sens"] != "vente"):
        port_apres = appliquer_ordre(port_apres, j["ticker"], j["sens"], j["pourcentage"], j["operation"])
    details = []
    for j in jambes:
        for d in contraintes_strictes(fiche, j["ticker"], j["sens"], j["operation"])["detail"]:
            details.append({**d, "ticker": j["ticker"]})
    violes = list(dict.fromkeys(d["theme"] for d in details if d["statut"] == "violee"))
    cs = {"violee": bool(violes), "themes_violes": violes, "detail": details}
    avant = evaluer(port_avant, fiche)
    apres = min((evaluer(port_apres, fiche, j) for j in jambes), key=lambda ev: ev["score"])
    dirn = direction(avant["score"], apres["score"])
    if cs["violee"]:
        dirn["remarque"] = "Direction lue sur les notes seulement : une contrainte stricte est violée, l'ordre est incompatible."
    operation = next((j["operation"] for j in jambes if j["operation"] != "comptant"), "comptant")
    resultat = {
        "ordre": jambes[0],
        "ordres": jambes,
        "portefeuille_avant_pct": port_avant,
        "portefeuille_apres_pct": port_apres,
        "contraintes_strictes": cs,
        "avant": avant,
        "apres": apres,
        "verdict": verdict(cs, apres["score"]),
        "direction": dirn,
        "contribution_risque_apres": contribution_risque(port_apres, jambes[0]["ticker"]),
        "operation": bloc_operation(port_avant, port_apres, operation, fiche, apres),
        "cause": cause(fiche, jambes, cs, apres, port_apres),
    }
    resultat["points_attention"] = points_attention(fiche, resultat["operation"])
    return resultat


# ---------------------------------------------------------------- points d'attention (faits, aucune note)

RISQUES_OPERATIONS = {
    "marge": "une partie de l'achat est payée avec de l'argent emprunté : les gains comme les pertes portent sur plus "
             "que la valeur nette du portefeuille",
    "decouvert": "la perte n'a pas de plafond si le prix de l'instrument monte",
}


def points_attention(fiche: dict, bloc_op: dict) -> list:
    """Faits à garder en vue pour lire l'ordre, sans note ni verdict : l'opération avancée et son risque (avec le
    levier calculé), l'expérience, l'objectif et l'horizon déclarés, et les limites déjà dites par le moteur."""
    q = references.charger("questionnaire")
    reponses = fiche["questionnaire"]

    def libelle(champ):
        option = q[champ]["options"].get(reponses.get(champ), reponses.get(champ))
        return option.get("libelle") if isinstance(option, dict) else option

    points = []
    code = bloc_op.get("code", "comptant")
    if code != "comptant":
        levier = f"{bloc_op.get('levier_apres', 1.0):.2f}".replace(".", ",")
        points.append({"type": "operation", "operation": code,
                       "texte": f"{LIBELLES_OPERATIONS[code]} : opération avancée ; {RISQUES_OPERATIONS[code]}. "
                                f"Levier après l'ordre : {levier}."})
    points.append({"type": "profil_declare", "experience": reponses.get("experience"),
                   "objectif": reponses.get("objectif"), "horizon": reponses.get("horizon"),
                   "texte": f"Profil déclaré : expérience « {libelle('experience')} », objectif « {libelle('objectif')} », "
                            f"horizon « {libelle('horizon')} »."})
    for limite in bloc_op.get("limites") or []:
        points.append({"type": "limite", "texte": limite})
    return points
