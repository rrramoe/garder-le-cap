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
from . import apport as _apport
from . import donnees, instruments, notation, references, solidite as _solidite
from . import faits_marche as _faits
from . import profils as _profils

NOTE_DE_PASSAGE = notation.NOTE_DE_PASSAGE  # lue par l'interface ; chaque résultat la porte aussi

SOURCES_FICHE_CLIENT = ("fbngp_profils_2024", "fbngp_politique_2022", "fidelity_crypto_2026", "hypothese_personas",
                        "hypothese_crypto_correspondance", "hypothese_plafonds_tous_profils", "hypothese_classes",
                        "hypothese_coherence_objectif", "acvm_capacite_perte", "hypothese_capacite_libelles")
SOURCES_NOTATION = ("donnees_marche", "fbngp_repartition_actions_2024", "rbcgam_fourchettes_regionales_2025", "hypothese_geographie", "hypothese_besoin_liquidite", "acvm_81_102_annexe_f", "hypothese_risque_familles", "donnees_dividendes", "hypothese_objectif", "fbngp_pire_annee_2024", "hypothese_conventions_calcul", "fbngp_profils_2024", "fbngp_politique_2022",
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
    deduites = [e[k] for e in fiche["deduit"].values() for k in ("regle", "hypothese") if e.get(k)]
    fiche["sources"] = _sources(*SOURCES_FICHE_CLIENT, *deduites)
    return fiche


@_api
def lire_fiche_instrument(ticker: str, montant_cad: float | None = None) -> dict:
    """Classe, devise, secteur, statistiques en CAD, étiquettes, faits de marché et leurs sources.

    `montant_cad` (facultatif) : montant d'un ordre en dollars canadiens ; la fiche dit alors ce qu'il
    représente en séances de la valeur échangée moyenne (`faits_marche.liquidite.jours_de_volume_ordre`).
    """
    f = dict(instruments.fiche(str(ticker).strip().upper()))
    cles = {"donnees_marche", "hypothese_etiquettes", "hypothese_classes"}
    f["profil"] = _profils.profil(f["symbole"])
    if f["profil"].get("source"):
        cles.add(f["profil"]["source"])
    if f.get("faits_marche"):
        cles |= set(f["faits_marche"].get("sources", []))
        if montant_cad is not None:
            fm = dict(f["faits_marche"])
            fm["liquidite"] = {**fm["liquidite"], "montant_ordre_cad": float(montant_cad),
                               "jours_de_volume_ordre": _faits.jours_de_volume(float(montant_cad), fm["liquidite"])}
            f["faits_marche"] = fm
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


def _operation(operation) -> str:
    return str(operation or "comptant").strip().lower()


@_api
def simuler_ordre(client, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
    """Contraintes strictes, notes avant et après, score, verdict, direction.

    `operation` : « comptant » (par défaut), « marge » (achat sur marge) ou « decouvert » (vente à découvert).
    """
    fiche = _client.construire_fiche(client)
    op = _operation(operation)
    r = notation.simuler(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage, op)
    r["solidite"] = _solidite.solidite(r["portefeuille_apres_pct"], fiche, r["apres"])
    cles = list(SOURCES_NOTATION) + [d["source"] for d in r["contraintes_strictes"]["detail"] if d.get("source")]
    cles.append("hypothese_solidite")
    cles += notation.SOURCES_OPERATIONS[op]
    return {"client": fiche["id"], **r, "score": r["apres"]["score"], "dimension_min": r["apres"]["dimension_min"],
            "mesure_min": r["apres"]["mesure_min"], "periode": _periode_donnees(), "sources": _sources(*cles)}


@_api
def simuler_scenario(client, ordres: list) -> dict:
    """Plusieurs ordres (1 à 4) appliqués ensemble : même résultat que `simuler_ordre`, plus `ordres`.

    Chaque ordre : `{ticker, sens, pourcentage}` (+ `operation`). Les ventes sont versées à l'encaisse et
    paient les achats ; leur total ne dépasse pas celui des achats.
    """
    fiche = _client.construire_fiche(client)
    r = notation.simuler_scenario(fiche, ordres)
    r["solidite"] = _solidite.solidite(r["portefeuille_apres_pct"], fiche, r["apres"])
    cles = list(SOURCES_NOTATION) + [d["source"] for d in r["contraintes_strictes"]["detail"] if d.get("source")]
    cles.append("hypothese_solidite")
    for j in r["ordres"]:
        cles += notation.SOURCES_OPERATIONS.get(j["operation"], ())
    return {"client": fiche["id"], **r, "score": r["apres"]["score"], "dimension_min": r["apres"]["dimension_min"],
            "mesure_min": r["apres"]["mesure_min"], "periode": _periode_donnees(),
            "sources": _sources(*dict.fromkeys(cles))}


@_api
def chercher_taille_compatible(client, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
    """Plus grande taille (pas de 0,5 %) avec score >= 50, et courbe du score selon la taille."""
    fiche = _client.construire_fiche(client)
    op = _operation(operation)
    r = notation.taille_compatible(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage, op)
    resultat = {"client": fiche["id"], "ticker": str(ticker).strip().upper(), "sens": sens, **r,
                "periode": _periode_donnees(), "sources": _sources(*SOURCES_NOTATION, *notation.SOURCES_OPERATIONS[op])}
    if op != "comptant":
        resultat["operation"] = op
    return resultat


@_api
def solidite(client, ticker: str, sens: str, pourcentage: float) -> dict:
    """Solidité du score après l'ordre : note de risque sur 2022 seule et sur la période sans 2022."""
    fiche = _client.construire_fiche(client)
    r = notation.simuler(fiche, str(ticker).strip().upper(), str(sens).strip().lower(), pourcentage)
    return {"client": fiche["id"], "ordre": r["ordre"], "verdict": r["verdict"],
            **_solidite.solidite(r["portefeuille_apres_pct"], fiche, r["apres"]),
            "periode": _periode_donnees(), "sources": _sources(*SOURCES_NOTATION, "hypothese_solidite")}


@_api
def origine_references() -> dict:
    """D'où les fichiers de référence ont été lus (Amazon S3 ou dossier local), pour la partie 8 du rapport."""
    return {**references.origine(), "sources": _sources("hypothese_classes")}


@_api
def decrire_apport(client, ticker: str, pourcentage: float | None = None) -> dict:
    """Ce que l'instrument apporterait au portefeuille : des faits, sans note ni verdict.

    Corrélation avec le portefeuille, trois positions les plus proches, exposition actuelle à sa classe,
    son secteur et ses étiquettes (avec la limite de la politique quand il y en a une), part du portefeuille
    et du risque après un achat de `pourcentage` %, et les instruments de la même classe classés par proximité.
    """
    fiche = _client.construire_fiche(client)
    if pourcentage is not None:
        try:
            pourcentage = float(pourcentage)
        except (TypeError, ValueError):
            return {"erreur": f"Montant invalide : « {pourcentage} ». Indiquez un pourcentage du portefeuille."}
    r = _apport.decrire(fiche, str(ticker).strip().upper(), pourcentage)
    periode = _periode_donnees()
    for bloc in ("correlation_portefeuille", "exposition_actuelle"):
        r[bloc]["periode"] = periode
    return {"client": fiche["id"], **r, "periode": periode, "frequence": "quotidienne",
            "sources": _sources("donnees_marche", "hypothese_conventions_calcul", "hypothese_classes",
                                "hypothese_etiquettes", "fbngp_profils_2024", "fbngp_politique_2022",
                                "hypothese_plafonds_tous_profils", "fidelity_crypto_2026",
                                "hypothese_crypto_correspondance", "hypothese_mecanique_ordre")}
