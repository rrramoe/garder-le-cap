"""API publique du moteur : seul point d'entrée de l'agent et de l'interface.

Chaque fonction renvoie un dictionnaire sérialisable en JSON avec un champ `sources`,
ou `{"erreur": "..."}` en cas de problème : aucune exception ne sort de l'API.

Partout où un client est attendu : un identifiant de persona (« robert », « mateo »,
« amira ») ou une fiche (dictionnaire) dont on a modifié des réponses, par exemple
`{"persona": "robert", "questionnaire": {"horizon": "15_plus"}}`.
"""
from __future__ import annotations

import functools
import math

import numpy as np

from . import client as _client
from . import donnees, instruments, notation, references, solidite as _solidite

SOURCES_FICHE_CLIENT = ("fbngp_profils_2024", "fbngp_politique_2022", "fidelity_crypto_2026", "hypothese_personas",
                        "hypothese_crypto_correspondance", "hypothese_plafonds_tous_profils", "hypothese_classes",
                        "hypothese_coherence_objectif")
SOURCES_NOTATION = ("donnees_marche", "hypothese_conventions_calcul", "fbngp_profils_2024", "fbngp_politique_2022",
                    "fidelity_crypto_2026", "hypothese_etalons", "hypothese_echelle", "hypothese_classes",
                    "hypothese_crypto_correspondance", "hypothese_plafonds_tous_profils", "hypothese_mecanique_ordre")


def _nettoyer(x):
    """Rend un objet sérialisable en JSON (types numpy, NaN, arrondis)."""
    if isinstance(x, dict):
        return {str(k): _nettoyer(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_nettoyer(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, 6)
    return x


def _api(fonction):
    @functools.wraps(fonction)
    def enveloppe(*args, **kwargs):
        try:
            return _nettoyer(fonction(*args, **kwargs))
        except (donnees.ErreurDonnees, instruments.ErreurInstrument, _client.ErreurClient, notation.ErreurOrdre,
                FileNotFoundError) as e:
            return {"erreur": str(e)}
        except Exception as e:  # aucune exception ne sort de l'API
            return {"erreur": f"Erreur inattendue du moteur ({type(e).__name__}) : {e}"}
    return enveloppe


def _periode_donnees() -> dict:
    p = donnees.periode()
    return {"debut": p["debut"], "fin": p["fin"], "devise": "CAD"}


def _sources(*cles) -> list:
    return references.sources(*cles)


@_api
def lire_fiche_client(client) -> dict:
    """Profil, horizon, règles, fourchettes et portefeuille du client."""
    fiche = _client.construire_fiche(client)
    fiche["poids_par_classe_pct"] = _client.poids_par_classe(fiche["portefeuille_pct"])
    fiche["sources"] = _sources(*SOURCES_FICHE_CLIENT)
    return fiche


@_api
def lire_fiche_instrument(ticker: str) -> dict:
    """Classe, devise, secteur, statistiques en CAD, étiquettes et leurs sources."""
    f = dict(instruments.fiche(str(ticker).strip().upper()))
    cles = {"donnees_marche", "hypothese_etiquettes", "hypothese_classes"}
    cles |= {e["source"] for e in f["etiquettes"].values() if e.get("source")}
    f["periode"] = instruments.meta().get("periode")
    f["fiches_generees_le"] = instruments.meta().get("genere_le")
    f["seuil_speculatif"] = instruments.meta().get("seuil_speculatif")
    f["sources"] = _sources(*sorted(cles))
    return f


@_api
def lister_instruments(classe: str | None = None) -> dict:
    """Instruments de l'univers, filtrés par classe de la politique (liquidites, revenu_fixe, actions, alternatifs)."""
    classes = references.charger("classes")["classes"]
    if classe not in (None, "", "toutes") and classe not in classes:
        return {"erreur": f"Classe inconnue : « {classe} ». Choix possibles : {', '.join(classes)}."}
    liste = []
    for t, f in instruments.toutes().items():
        if classe in (None, "", "toutes") or f["classe_politique"] == classe:
            liste.append({"symbole": t, "nom": f["nom"], "classe_politique": f["classe_politique"],
                          "classe_actif": f["classe_actif"], "secteur": f["secteur"], "devise": f["devise"],
                          "etiquettes": {k: v["valeur"] for k, v in f["etiquettes"].items()},
                          "volatilite_annualisee": f["statistiques_cad"]["volatilite_annualisee"],
                          "pire_baisse": f["statistiques_cad"]["pire_baisse"]})
    return {"classe": classe or "toutes", "instruments": liste, "nombre": len(liste),
            "sources": _sources("donnees_marche", "hypothese_classes", "hypothese_etiquettes")}


@_api
def etat_des_lieux(client) -> dict:
    """Notes du portefeuille actuel, sans ordre."""
    fiche = _client.construire_fiche(client)
    ev = notation.evaluer(fiche["portefeuille_pct"], fiche)
    return {"client": fiche["id"], "portefeuille_pct": fiche["portefeuille_pct"], **ev,
            "statut": "dans_la_politique" if ev["dans_la_politique"] else "hors_politique",
            "periode": _periode_donnees(), "sources": _sources(*SOURCES_NOTATION)}


@_api
def simuler_ordre(client, ticker: str, sens: str, pourcentage: float) -> dict:
    """Contraintes strictes, notes avant et après, score, verdict, direction."""
    fiche = _client.construire_fiche(client)
    r = notation.simuler(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage)
    r["solidite"] = _solidite.solidite(r["portefeuille_apres_pct"], fiche, r["apres"])
    cles = list(SOURCES_NOTATION) + [d["source"] for d in r["contraintes_strictes"]["detail"] if d.get("source")]
    cles.append("hypothese_solidite")
    return {"client": fiche["id"], **r, "score": r["apres"]["score"], "dimension_min": r["apres"]["dimension_min"],
            "mesure_min": r["apres"]["mesure_min"], "periode": _periode_donnees(), "sources": _sources(*cles)}


@_api
def chercher_taille_compatible(client, ticker: str, sens: str, pourcentage: float) -> dict:
    """Plus grande taille (pas de 0,5 %) avec score >= 50, et courbe du score selon la taille."""
    fiche = _client.construire_fiche(client)
    r = notation.taille_compatible(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage)
    return {"client": fiche["id"], "ticker": str(ticker).strip().upper(), "sens": sens, **r,
            "periode": _periode_donnees(), "sources": _sources(*SOURCES_NOTATION)}


@_api
def solidite(client, ticker: str, sens: str, pourcentage: float) -> dict:
    """Solidité du score après l'ordre : note de risque sur 2022 seule et sur la période sans 2022."""
    fiche = _client.construire_fiche(client)
    r = notation.simuler(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage)
    return {"client": fiche["id"], "ordre": r["ordre"], "verdict": r["verdict"],
            **_solidite.solidite(r["portefeuille_apres_pct"], fiche, r["apres"]),
            "periode": _periode_donnees(), "sources": _sources(*SOURCES_NOTATION, "hypothese_solidite")}
