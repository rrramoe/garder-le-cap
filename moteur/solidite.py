"""Solidité du verdict (section 7.7 de la spécification).

La note de risque est recalculée sur deux fenêtres de l'historique :
- défavorable : l'année 2022 seule ;
- favorable : toute la période sans 2022.
Le score de chaque fenêtre est le minimum de cette note de risque et des notes de diversification et de
préférences, qui ne dépendent pas de l'historique. `solide` si le score est du même côté de la note de passage dans
les deux fenêtres, sinon `fragile`. Le score principal reste celui de la période complète.

Les formules sont celles de `notation` (note_ampleur, note_duree) ; seuls les rendements changent. Les
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


def note_risque_fenetre(port: dict, fiche: dict, fenetre: str) -> dict:
    """Note de risque (section 7.3) recalculée sur une fenêtre, avec les mêmes formules."""
    stats = statistiques_fenetre(port, fenetre)
    et = _etalons_fenetre(fiche["deduit"]["profil"]["valeur"], fenetre, str(donnees.dossier_donnees()))
    d, d_ref, d_lim = abs(stats["pire_baisse"]), abs(et["reference"]["pire_baisse"]), abs(et["limite"]["pire_baisse"])
    h = fiche["deduit"]["horizon_annees"]["valeur"]
    mesures = {
        "ampleur": {"note": notation.note_ampleur(d, d_ref, d_lim), "pire_baisse": -d,
                    "pire_baisse_reference": -d_ref, "pire_baisse_limite": -d_lim},
        "duree": {"note": notation.note_duree(stats["temps_sous_l_eau_annees"], h),
                  "temps_sous_l_eau_annees": stats["temps_sous_l_eau_annees"], "horizon_annees": h,
                  "non_recupere": stats["non_recupere"]},
    }
    mesure_min = min(mesures, key=lambda k: mesures[k]["note"])
    return {"note": mesures[mesure_min]["note"], "mesure_min": mesure_min, "mesures": mesures}


def solidite(port: dict, fiche: dict, evaluation: dict) -> dict:
    """Solidité du score `evaluation` (résultat de notation.evaluer sur `port`, période complète)."""
    autres = {k: v["note"] for k, v in evaluation["notes"].items()
              if k != "risque" and isinstance(v.get("note"), (int, float))}
    fenetres = {}
    for nom, libelle in FENETRES.items():
        rend = _rendements_fenetre(nom)
        risque = notation.convertir_famille(note_risque_fenetre(port, fiche, nom))
        notes = {"risque": risque["note"], **autres}
        dim = min(notes, key=notes.get)
        fenetres[nom] = {
            "libelle": libelle,
            "debut": rend.index[0].date().isoformat() if nom == "defavorable" else donnees.periode()["debut"],
            "fin": rend.index[-1].date().isoformat() if nom == "defavorable" else donnees.periode()["fin"],
            "note_risque": risque,
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
        "regle": (f"Note de risque recalculée sur 2022 seule et sur la période sans 2022 ; solide si la note de l'angle déterminant "
                  f"est du même côté de la note de passage ({notation.NOTE_DE_PASSAGE:g}) dans les deux, sinon fragile. "
                  "La note principale reste celle de la période complète."),
    }
