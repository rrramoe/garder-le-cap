"""Solidité du verdict (section 7.7 de la spécification).

Chaque mesure fondée sur l'historique est recalculée sur deux fenêtres :
- défavorable : l'année 2022 seule ;
- favorable : toute la période sans 2022.
Angle Risque : pire baisse, durée sous le sommet, fluctuations et pire année ; angle Objectif : capital préservé
quand c'est l'objectif. Les autres angles (liquidité, diversification, préférences, revenu, part des actions) ne
dépendent pas de l'historique et gardent leur note. Une mesure qu'une fenêtre est trop courte pour calculer est
`indetermine` dans cette fenêtre, avec sa raison, et ne décide pas. La note d'une fenêtre est celle de son angle
déterminant ; `solide` si elle est du même côté de la note de passage dans les deux fenêtres, sinon `fragile`.
La note principale reste celle de la période complète.

Les formules et les limites sont celles de `notation` ; seuls les rendements changent. Les
portefeuilles étalons du profil sont recalculés sur la même fenêtre que le portefeuille, pour que
l'ampleur compare des baisses de la même période. Hypothèse pour la fenêtre favorable : les rendements
d'avant et d'après 2022 sont mis bout à bout et les dates d'après 2022 sont avancées de 365 jours, pour
que la durée sous l'eau ne compte pas l'année retirée.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import donnees, notation, references

ANNEE_DEFAVORABLE = 2022
FENETRES = {
    "defavorable": "Une mauvaise année de marché",
    "favorable": "Le reste de la période",
}


def _rendements_fenetre(fenetre: str) -> pd.DataFrame:
    rend = donnees.rendements_cad()
    annee = rend.index.year
    if fenetre == "defavorable":
        return rend[annee == ANNEE_DEFAVORABLE]
    if fenetre == "favorable":
        avant, apres = rend[annee < ANNEE_DEFAVORABLE], rend[annee > ANNEE_DEFAVORABLE].copy()
        apres.index = apres.index - pd.Timedelta(days=365)
        return pd.concat([avant, apres])
    raise ValueError(f"Fenêtre inconnue : {fenetre}")


def valeur_fenetre(poids: dict, fenetre: str) -> pd.Series:
    """Valeur (base 1) du portefeuille à poids constants, rééquilibré chaque jour, sur la fenêtre."""
    poids = {t: float(w) for t, w in poids.items() if abs(float(w)) > 1e-12}
    total = sum(poids.values())
    if total <= 0:
        raise donnees.ErreurDonnees("Portefeuille vide : aucun poids positif.")
    rend = _rendements_fenetre(fenetre)
    w = pd.Series(poids) / total
    r = rend[w.index].fillna(0.0).to_numpy() @ w.to_numpy()
    premier = rend.index[0] - pd.Timedelta(days=1)
    return pd.Series(np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=rend.index.insert(0, premier))


def statistiques_fenetre(poids: dict, fenetre: str) -> dict:
    v = valeur_fenetre(poids, fenetre)
    tsl = donnees.temps_sous_l_eau(v)
    return {"pire_baisse": donnees.pire_baisse(v), "temps_sous_l_eau_annees": tsl["annees"],
            "non_recupere": tsl["non_recupere"]}


@lru_cache(maxsize=32)
def _etalons_fenetre(profil_id: str, fenetre: str, dossier: str) -> dict:
    f = references.charger("profils")["profils"][profil_id]["fourchettes"]
    reference = {c: v["cible"] for c, v in f.items()}
    limite = {c: 0.0 for c in f}
    limite["actions"] = f["actions"]["max"]
    limite["revenu_fixe"] = 100.0 - f["actions"]["max"]
    return {"reference": statistiques_fenetre(notation._poids_etalon(reference), fenetre),
            "limite": statistiques_fenetre(notation._poids_etalon(limite), fenetre)}


TROP_COURTE = "fenêtre trop courte pour cette mesure"


def _marquer_indetermine(m: dict) -> dict:
    if m.get("note") is None and m.get("statut") == "indetermine":
        m["raison"] = TROP_COURTE
    return m


def note_risque_fenetre(port: dict, fiche: dict, fenetre: str) -> dict:
    """Angle Risque recalculé sur une fenêtre, avec les mêmes formules et les mêmes limites que la période complète :
    pire baisse, durée sous le sommet, fluctuations et pire année. Note brute (limite à 50), comme `notation`."""
    stats = statistiques_fenetre(port, fenetre)
    v = valeur_fenetre(port, fenetre)
    profil_id = fiche["deduit"]["profil"]["valeur"]
    et = _etalons_fenetre(fiche["deduit"]["profil"]["valeur"], fenetre, str(donnees.dossier_donnees()))
    d, d_ref, d_lim = abs(stats["pire_baisse"]), abs(et["reference"]["pire_baisse"]), abs(et["limite"]["pire_baisse"])
    h = fiche["deduit"]["horizon_annees"]["valeur"]
    mesures = {
        "ampleur": {"note": notation.note_ampleur(d, d_ref, d_lim), "pire_baisse": -d,
                    "pire_baisse_reference": -d_ref, "pire_baisse_limite": -d_lim},
        "duree": {"note": notation.note_duree(stats["temps_sous_l_eau_annees"], h),
                  "temps_sous_l_eau_annees": stats["temps_sous_l_eau_annees"], "horizon_annees": h,
                  "non_recupere": stats["non_recupere"]},
        "fluctuations": _marquer_indetermine(notation.mesure_fluctuations(v, profil_id)),
        "pire_annee": _marquer_indetermine(notation.mesure_pire_annee(v, profil_id)),
    }
    return notation._noter(mesures)


def note_objectif_fenetre(port: dict, fiche: dict, fenetre: str, evaluation: dict) -> dict | None:
    """Angle Objectif recalculé sur la fenêtre quand sa mesure repose sur l'historique (préserver le capital) ;
    sinon None : la mesure (revenu, part des actions) ne dépend pas de la période."""
    if fiche["questionnaire"]["objectif"] != "preserver_capital":
        return None
    fam = notation.note_objectif(port, fiche, valeur=valeur_fenetre(port, fenetre))
    for m in fam["mesures"].values():
        _marquer_indetermine(m)
    return notation.convertir_famille(fam)


def solidite(port: dict, fiche: dict, evaluation: dict) -> dict:
    """Solidité du score `evaluation` (résultat de notation.evaluer sur `port`, période complète)."""
    fenetres = {}
    for nom, libelle in FENETRES.items():
        rend = _rendements_fenetre(nom)
        risque = notation.convertir_famille(note_risque_fenetre(port, fiche, nom))
        objectif = note_objectif_fenetre(port, fiche, nom, evaluation)
        familles = {k: v["note"] for k, v in evaluation["notes"].items()}   # angles qui ne dépendent pas de l'historique
        familles["risque"] = risque["note"]
        if objectif is not None:
            familles["objectif"] = objectif["note"]
        notes = {k: n for k, n in familles.items() if isinstance(n, (int, float))}   # indetermine : ne décide pas
        dim = min(notes, key=notes.get)
        fenetres[nom] = {
            "libelle": libelle,
            "debut": rend.index[0].date().isoformat() if nom == "defavorable" else donnees.periode()["debut"],
            "fin": rend.index[-1].date().isoformat() if nom == "defavorable" else donnees.periode()["fin"],
            "note_risque": risque,
            "note_objectif": objectif,
            "mesures_indeterminees": [k for k, m in risque["mesures"].items() if m.get("raison") == TROP_COURTE]
                                     + ([k for k, m in objectif["mesures"].items() if m.get("raison") == TROP_COURTE]
                                        if objectif else []),
            "score": notes[dim],
            "dimension_min": dim,
            "dans_la_politique": notes[dim] >= notation.SEUIL_COMPATIBLE,
        }
    cotes = {f["dans_la_politique"] for f in fenetres.values()}
    solide = len(cotes) == 1
    return {
        "statut": "solide" if solide else "fragile",
        "libelle": "Solide" if solide else "Fragile",
        "explication": ("Le verdict est le même dans les deux périodes." if solide else
                        "Le verdict change selon la période : il dépend de la "
                        "période retenue."),
        "score_principal": evaluation["score"],
        "fenetres": fenetres,
        "regle": (f"Mesures fondées sur l'historique (pire baisse, durée sous le sommet, fluctuations, pire année, et "
                  f"capital préservé quand c'est l'objectif) recalculées sur 2022 seule et sur la période sans 2022, avec "
                  f"les mêmes formules et limites ; une mesure qu'une fenêtre est trop courte pour calculer est "
                  f"indéterminée et ne décide pas ; solide si la note de l'angle déterminant "
                  f"est du même côté de la note de passage ({notation.NOTE_DE_PASSAGE:g}) dans les deux, sinon fragile. "
                  "La note principale reste celle de la période complète."),
    }
