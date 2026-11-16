"""Mémoire des analyses : une analyse identique en cours est partagée, une analyse finie est rejouée.

    partager(cle, calculer, sur_etape=None, relancer=False) -> dict

Deux demandes identiques (même fiche, même portefeuille, même ordre, mêmes réglages : la `cle`) partagent l'analyse
en cours : la seconde reçoit les étapes déjà faites, puis les suivantes au moment où elles arrivent, et le même
résultat. Une analyse finie et réussie est gardée (en mémoire pour la vie du processus, et dans un fichier local
pour qu'un autre processus, le script de préchauffage, puisse la remplir) puis rejouée avec ses étapes, marquée
`memoire.statut = "deja_faite"`. Une analyse en échec ou en repli n'est pas gardée. Sûr entre fils ; taille bornée.
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

TAILLE_MAX = 64
ATTENTE_MAX_S = 300
MESSAGE_DEJA_FAITE = "Analyse déjà faite pour cet ordre : elle est rejouée. « Relancer » en refait une nouvelle."
FICHIER_DEFAUT = Path(__file__).resolve().parent.parent / ".cache" / "analyses.json"


def fichier() -> Path:
    return Path(os.environ.get("GLC_MEMOIRE_FICHIER") or FICHIER_DEFAUT)


class _EnCours:
    def __init__(self):
        self.verrou = threading.Lock()
        self.evenements: list = []
        self.auditeurs: list = []
        self.fini = threading.Event()
        self.resultat = None

    def diffuser(self, evenement: dict) -> None:
        with self.verrou:
            self.evenements.append(evenement)
            auditeurs = list(self.auditeurs)
        for f in auditeurs:
            try:
                f(evenement)
            except Exception:
                pass

    def ecouter(self, sur_etape) -> None:
        """Rejoue les étapes déjà faites à un nouvel auditeur, puis l'abonne aux suivantes."""
        if sur_etape is None:
            return
        with self.verrou:
            deja = list(self.evenements)
            self.auditeurs.append(sur_etape)
        for e in deja:
            try:
                sur_etape(e)
            except Exception:
                pass


_verrou = threading.Lock()
_en_cours: dict = {}
_finies: "OrderedDict[str, dict]" = OrderedDict()


def gardable(r: dict) -> bool:
    """Une analyse réussie : une explication, sans erreur, sans garde-fou intervenu, sans repli de l'explorateur."""
    if not isinstance(r, dict) or r.get("erreur") or not r.get("explication"):
        return False
    if (r.get("garde_fou") or {}).get("intervenu"):
        return False
    return not any(a.get("statut") == "repli" for a in r.get("agents") or [] if isinstance(a, dict))


def _lire_fichier() -> dict:
    try:
        return json.loads(fichier().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ecrire_fichier(cle: str, entree: dict) -> None:
    try:
        f = fichier()
        f.parent.mkdir(parents=True, exist_ok=True)
        donnees = _lire_fichier()
        donnees[cle] = entree
        while len(donnees) > TAILLE_MAX:
            donnees.pop(next(iter(donnees)))
        temporaire = f.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        temporaire.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
        os.replace(temporaire, f)
    except Exception:
        pass


def _garder(cle: str, resultat: dict, evenements: list) -> None:
    entree = {"resultat": resultat, "evenements": evenements, "garde_le": time.time()}
    with _verrou:
        _finies[cle] = entree
        _finies.move_to_end(cle)
        while len(_finies) > TAILLE_MAX:
            _finies.popitem(last=False)
        _ecrire_fichier(cle, entree)


def _trouver(cle: str) -> dict | None:
    with _verrou:
        if cle in _finies:
            _finies.move_to_end(cle)
            return _finies[cle]
    entree = _lire_fichier().get(cle)
    if isinstance(entree, dict) and gardable(entree.get("resultat")):
        with _verrou:
            _finies[cle] = entree
        return entree
    return None


def completer(cle: str, champs: dict) -> None:
    """Ajoute des champs à une analyse gardée (par exemple l'identifiant de sa trace, une fois écrite)."""
    with _verrou:
        entree = _finies.get(cle)
        if entree is None:
            return
        entree["resultat"].update(copy.deepcopy(champs))
        _ecrire_fichier(cle, entree)


def oublier(cle: str | None = None) -> None:
    """Vide la mémoire (toute, ou une seule analyse) ; le fichier local n'est pas touché."""
    with _verrou:
        if cle is None:
            _finies.clear()
        else:
            _finies.pop(cle, None)


def partager(cle: str, calculer, sur_etape=None, relancer: bool = False) -> dict:
    """`calculer(diffuser)` fait l'analyse en envoyant ses étapes à `diffuser` ; il est appelé au plus une fois par
    analyse identique en cours."""
    if not relancer:
        entree = _trouver(cle)
        if entree is not None:
            for e in entree.get("evenements") or []:
                try:
                    if sur_etape is not None:
                        sur_etape(e)
                except Exception:
                    pass
            r = copy.deepcopy(entree["resultat"])
            r["memoire"] = {"statut": "deja_faite", "message": MESSAGE_DEJA_FAITE, "garde_le": entree.get("garde_le")}
            return r
    with _verrou:
        courant = _en_cours.get(cle)
        proprietaire = courant is None
        if proprietaire:
            courant = _en_cours[cle] = _EnCours()
    if not proprietaire:
        courant.ecouter(sur_etape)
        if courant.fini.wait(ATTENTE_MAX_S) and courant.resultat is not None:   # sinon : sa propre analyse
            r = copy.deepcopy(courant.resultat)
            r["memoire"] = {"statut": "partagee", "message": "Analyse partagée avec une demande identique en cours."}
            return r
        proprietaire = True                      # l'analyse partagée n'a pas fini à temps : on en fait une
        courant = _EnCours()
    courant.ecouter(sur_etape)
    resultat = None
    try:
        resultat = calculer(courant.diffuser)
    finally:
        # Toujours : l'auditeur ne reste jamais à attendre, même si le calcul a levé (il fera alors le sien).
        courant.resultat = resultat
        with _verrou:
            if _en_cours.get(cle) is courant:
                del _en_cours[cle]
        courant.fini.set()
    if gardable(resultat):
        _garder(cle, copy.deepcopy(resultat), list(courant.evenements))
    r = dict(resultat)
    r["memoire"] = {"statut": "nouvelle"}
    return r
