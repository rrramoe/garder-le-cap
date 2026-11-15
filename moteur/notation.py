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

def appliquer_ordre(port: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    """Portefeuille après l'ordre. Achat payé par l'encaisse, vente versée à l'encaisse."""
    cash = references.encaisse()
    instruments.fiche(ticker)
    if sens not in ("achat", "vente"):
        raise ErreurOrdre(f"Sens invalide : « {sens} ». Choix possibles : achat, vente.")
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
        if pct > dispo + EPS:
            raise ErreurOrdre(
                f"Encaisse insuffisante : l'achat de {pct:g} % dépasse l'encaisse disponible ({cash}, {dispo:g} % du portefeuille). "
                "L'achat sur marge n'est pas simulé (hypothèse du projet)."
            )
        nouveau[cash] = dispo - pct
        nouveau[ticker] = nouveau.get(ticker, 0.0) + pct
    else:
        detenu = nouveau.get(ticker, 0.0)
        if pct > detenu + EPS:
            raise ErreurOrdre(f"Vente impossible : le portefeuille détient {detenu:g} % de {ticker}, moins que les {pct:g} % demandés.")
        nouveau[ticker] = detenu - pct
        nouveau[cash] = nouveau.get(cash, 0.0) + pct
    return {t: w for t, w in nouveau.items() if w > EPS}


# ---------------------------------------------------------------- contraintes strictes

def contraintes_strictes(fiche: dict, ticker: str, sens: str) -> dict:
    """Section 7.1 : vérifiées pour un achat seulement."""
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
    mesure_min = min(mesures, key=lambda k: mesures[k]["note"])
    return {"note": mesures[mesure_min]["note"], "mesure_min": mesure_min, "mesures": mesures,
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
    mesures = {}
    for c, f in fourchettes.items():
        w = classes.get(c, 0.0)
        mesures[f"classe_{c}"] = {"note": note_classe(w, f["min"], f["cible"], f["max"]), "poids": w,
                                  "min": f["min"], "cible": f["cible"], "max": f["max"],
                                  "libelle": f"Poids de la classe « {c} » face à sa fourchette"}
    w_crypto = sum(w for t, w in port.items() if instruments.fiche(t)["classe_actif"] == "crypto")
    mesures["crypto"] = {"note": _plafond(w_crypto, crypto["plafond_pct"]), "poids": w_crypto,
                         "plafond": crypto["plafond_pct"], "libelle": "Poids des cryptoactifs face au plafond du profil"}

    actions = {t: w for t, w in port.items() if instruments.est_action_individuelle(t)}
    fonds = {t: w for t, w in port.items() if instruments.est_fonds(t)}
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
    mesure_min = min(mesures, key=lambda k: mesures[k]["note"])
    return {"note": mesures[mesure_min]["note"], "mesure_min": mesure_min, "mesures": mesures,
            "poids_par_classe": classes}


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
            portes = {t: w for t, w in port.items() if instruments.valeur_etiquette(t, etiquette) is True}
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
    if not mesures:
        return {"note": 100.0, "mesure_min": None, "sans_objet": True, "mesures": {}, "signalements": [],
                "libelle": "Aucune préférence souple : sans objet."}
    mesure_min = min(mesures, key=lambda k: mesures[k]["note"])
    return {"note": mesures[mesure_min]["note"], "mesure_min": mesure_min, "sans_objet": False, "mesures": mesures,
            "signalements": signalements}


# ---------------------------------------------------------------- score

def evaluer(port: dict, fiche: dict, ordre: dict | None = None) -> dict:
    notes = {
        "risque": note_risque(port, fiche),
        "diversification": note_diversification(port, fiche),
        "preferences": note_preferences(port, fiche, ordre),
    }
    dim = min(notes, key=lambda k: notes[k]["note"])
    score = notes[dim]["note"]
    return {"score": score, "dimension_min": dim, "mesure_min": notes[dim]["mesure_min"], "notes": notes,
            "dans_la_politique": score >= SEUIL_COMPATIBLE}


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


def simuler(fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    port_avant = fiche["portefeuille_pct"]
    port_apres = appliquer_ordre(port_avant, ticker, sens, pourcentage)
    ordre = {"ticker": ticker, "sens": sens, "pourcentage": float(pourcentage)}
    cs = contraintes_strictes(fiche, ticker, sens)
    avant = evaluer(port_avant, fiche)
    apres = evaluer(port_apres, fiche, ordre)
    dirn = direction(avant["score"], apres["score"])
    if cs["violee"]:
        dirn["remarque"] = "Direction lue sur les notes seulement : une contrainte stricte est violée, l'ordre est incompatible."
    return {
        "ordre": ordre,
        "portefeuille_avant_pct": port_avant,
        "portefeuille_apres_pct": port_apres,
        "contraintes_strictes": cs,
        "avant": avant,
        "apres": apres,
        "verdict": verdict(cs, apres["score"]),
        "direction": dirn,
        "contribution_risque_apres": contribution_risque(port_apres, ticker),
    }


def taille_compatible(fiche: dict, ticker: str, sens: str, pourcentage: float) -> dict:
    """Plus grande taille, par pas de 0,5 %, jusqu'au montant demandé, avec score >= 50."""
    port = fiche["portefeuille_pct"]
    appliquer_ordre(port, ticker, sens, pourcentage)  # valide l'ordre demandé
    cs = contraintes_strictes(fiche, ticker, sens)
    if cs["violee"]:
        return {"lancee": False, "taille_compatible_pct": None, "courbe": [], "contraintes_strictes": cs,
                "raison": "Contrainte stricte violée : aucune taille ne réparerait la violation."}
    n = int(np.floor(float(pourcentage) / PAS_TAILLE + 1e-9))
    tailles = [round(PAS_TAILLE * k, 4) for k in range(1, n + 1)]
    if not tailles or abs(tailles[-1] - float(pourcentage)) > 1e-9:
        tailles.append(float(pourcentage))
    courbe = []
    for x in tailles:
        ev = evaluer(appliquer_ordre(port, ticker, sens, x), fiche, {"ticker": ticker, "sens": sens, "pourcentage": x})
        courbe.append({"taille_pct": x, "score": ev["score"], "dimension_min": ev["dimension_min"], "mesure_min": ev["mesure_min"]})
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
