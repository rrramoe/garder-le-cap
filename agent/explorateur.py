"""Agent explorateur : envoyé par le chef de dossier pour un ordre « en tension », il cherche et teste des pistes.

    explorer(client, ordre, mission, simulation, modele=None, sur_etape=None, compteur=None) -> dict

Le code fixe ce qui est une règle : l'en-tête des faits (ordre, résultat du moteur, cause, portefeuille, thèmes),
les outils et leur borne de quatre pistes, la limite de tours, le délai, et le repli sur la taille compatible
calculée par le code si l'explorateur échoue. Ne lève jamais d'exception.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as DelaiDepasse
from pathlib import Path

from moteur import api

from .outils import (LIMITE_PISTES, compacter_apport, compacter_simulation, creer_outils_explorateur,
                     identifiant_client)
from .suivi import Suivi

PROMPT_EXPLORATEUR = Path(__file__).parent / "prompts" / "explorateur.md"
PROMPT_MANDAT = Path(__file__).parent / "prompts" / "explorateur_mandat.md"   # sous le mandat du chef (CHEF)
LIMITE_TOURS_EXPLORATEUR = 8     # deux tours d'essais (en parallèle), un essai refusé à corriger, le compte rendu
DELAI_EXPLORATEUR_S = 150
AVIS_REPLI = ("L'explorateur n'a pas pu finir : seule la taille compatible calculée par le code est montrée.")
AVIS_REPLI_REMPLACER = ("L'explorateur n'a pas pu finir sa recherche d'un autre instrument, et aucun montant ne "
                        "répare une règle stricte : aucune piste n'est montrée.")
AVIS_REPLI_SANS_PISTE = ("L'explorateur n'a pas pu finir, et une taille réduite de cette opération avancée n'est pas "
                         "proposée à un client débutant : aucune piste n'est montrée.")


def _theme_lisible(themes: dict) -> dict:
    return {k: v for k, v in (themes or {}).items() if v != "neutre"}


def _valeur(element):
    return element.get("valeur") if isinstance(element, dict) and "valeur" in element else element


def _sans_meta(x):
    """Une valeur déduite sans son origine ni sa source : {valeur, origine, source} → valeur."""
    if isinstance(x, dict) and "valeur" in x:
        return _sans_meta(x["valeur"])
    if isinstance(x, dict):
        return {k: _sans_meta(v) for k, v in x.items() if k not in ("origine", "source", "sources")}
    if isinstance(x, list):
        return [_sans_meta(v) for v in x]
    return x


def faits_client(fiche: dict) -> dict:
    """Tout ce que l'outil sait du client, de façon générique : chaque réponse de la fiche, la politique qui en est
    déduite et le portefeuille. Une réponse ajoutée à la fiche arrive ici sans changer ce code."""
    exclus = {"sources", "questionnaire", "deduit"}
    faits = {k: _sans_meta(v) for k, v in fiche.items() if k not in exclus}
    faits["reponses"] = fiche.get("questionnaire") or {}
    faits["politique_deduite"] = _sans_meta(fiche.get("deduit") or {})
    return faits


def _chemin(d, *cles):
    for c in cles:
        d = d.get(c) if isinstance(d, dict) else None
    return d


def faits_instrument(f: dict) -> dict:
    """L'instrument en peu de mots : identité, statistiques, étiquettes (toutes, quelles qu'elles soient), quelques
    faits de marché et son profil (entreprise ou fonds), sans sources ni dates de collecte."""
    s = f.get("statistiques_cad") or {}
    fm = f.get("faits_marche") or {}
    faits = {"symbole": f.get("symbole"), "nom": f.get("nom"), "classe_politique": f.get("classe_politique"),
             "classe_actif": f.get("classe_actif"), "secteur": f.get("secteur"), "devise": f.get("devise"),
             "volatilite_annualisee": s.get("volatilite_annualisee"), "pire_baisse": s.get("pire_baisse"),
             "etiquettes": {k: v.get("valeur") for k, v in (f.get("etiquettes") or {}).items()}}
    if fm:
        faits["faits_marche"] = {
            "pire_annee": _chemin(fm, "performance", "pire_annee"),
            "baisses_de_plus_de_20_pct": _chemin(fm, "risque", "baisses_de_plus_de_20_pct"),
            "beta": {m: v.get("beta") for m, v in (fm.get("marches") or {}).items() if isinstance(v, dict)},
            "rendement_dividende": _chemin(fm, "revenu", "rendement_dividende"),
            "correlation_avec_taux_10_ans": _chemin(fm, "taux", "correlation_avec_taux_10_ans")}
    if isinstance(f.get("profil"), dict):
        faits["profil"] = {k: v for k, v in f["profil"].items() if k not in ("source", "recupere_le", "sources")}
    return faits


def operations_avancees_permises(fiche: dict) -> bool:
    """Règle du code : pour un client débutant, aucune piste n'utilise l'achat sur marge ou la vente à découvert."""
    return (fiche.get("questionnaire") or {}).get("experience") != "debutante"


def pistes_permises(ordre: dict, avancees: bool, mode: str) -> str:
    """Les familles de pistes que les outils accepteront, dites d'avance pour ne pas gaspiller d'essais."""
    if mode == "remplacer":
        return "seulement un autre instrument (seul, ou payé par une vente) : pas de montant plus petit de l'ordre"
    if not avancees and (ordre.get("operation") or "comptant") != "comptant":
        return ("seulement des pistes au comptant : ni montant plus petit de cette opération avancée, ni vente d'un "
                "titre non détenu ; un achat ou une vente au comptant de positions détenues")
    if not avancees:
        return "toutes les familles, au comptant seulement"
    return "toutes les familles"


def entete(client, ordre: dict, mission: str, simulation: dict, mode: str = "ajuster") -> str:
    """Message de l'explorateur : les faits lus par le code (client, instrument, apport, résultat de l'ordre), puis
    la mission écrite par le chef de dossier. L'explorateur n'a pas à relire ce que le chef de dossier a déjà lu."""
    op = ordre.get("operation") or "comptant"
    fiche = api.lire_fiche_client(client)
    avancees = operations_avancees_permises(fiche)
    resultat = compacter_simulation(simulation)
    resultat["score_avant"] = (simulation.get("avant") or {}).get("score")
    avant = simulation.get("avant") or {}
    resultat["portefeuille_deja_hors_politique"] = (not avant["dans_la_politique"]) if "dans_la_politique" in avant \
        else None     # le seuil est celui du moteur, jamais écrit ici
    resultat["autres_mesures_sous_le_seuil"] = (simulation.get("cause") or {}).get("autres_mesures_sous_le_seuil")
    resultat.pop("portefeuille_apres_pct", None)
    resultat["points_attention"] = [p.get("texte") for p in simulation.get("points_attention") or []]
    faits = {
        "client_id": identifiant_client(client),
        "ordre_simule": {k: ordre[k] for k in ("ticker", "sens", "pourcentage")} | ({"operation": op} if op != "comptant" else {}),
        "resultat_de_l_ordre": resultat,
        "client": faits_client(fiche),
        "operations_avancees_permises": avancees,
        "pistes_permises": pistes_permises(ordre, avancees, mode),
        "mandat": ("remplacer : l'ordre viole une règle stricte, aucun montant ne la répare ; seules les pistes qui "
                   "remplacent l'instrument (seules, ou payées par une vente) sont acceptées, et aucune ne viole une "
                   "règle stricte" if mode == "remplacer" else "ajuster : l'ordre est en tension"),
        "instrument": faits_instrument(api.lire_fiche_instrument(ordre["ticker"])),
        "apport": compacter_apport(api.decrire_apport(client, ordre["ticker"], ordre["pourcentage"])),
    }
    # Le cadre « simulation » est écrit en clair : sans lui, le garde-fou Bedrock peut lire un ordre nu comme une
    # demande de transaction réelle et retenir le message.
    return ("Simulation éducative, aucun ordre réel n'est passé. Analyse d'un ordre simulé : faits établis par le "
            "code (ne les relis pas et ne les recalcule pas).\n"
            + json.dumps(faits, ensure_ascii=False, separators=(",", ":")) +
            "\n\nMandat du chef de dossier (simulation) :\n" + (mission or "(aucune précision)") +
            "\n\nTeste les pistes simulées, puis rends ton compte rendu.")


def lire_compte_rendu(texte: str | None) -> dict:
    """Les lignes du compte rendu : `intention` (la finalité supposée), `cause`, `retenues` (numéros d'essai) et
    `bilan` ; une ligne absente vaut None."""
    resultat = {"intention": None, "cause": None, "retenues": None, "bilan": None}
    for cle, nom in (("intention", r"(?:Finalit[ée] suppos[ée]e|Intention)"), ("cause", "Cause"),
                     ("retenues", r"Pistes retenues"), ("bilan", "Bilan")):
        m = re.search(rf"^[\W_]*{nom}[\W_]*:\s*(.+)$", texte or "", flags=re.MULTILINE | re.IGNORECASE)
        if m:
            resultat[cle] = m.group(1).strip().strip("*").strip()
    if resultat["retenues"] is not None:
        resultat["retenues"] = [int(n) for n in re.findall(r"\d+", resultat["retenues"])]
    return resultat


def retenir(pistes_et_essais: list, retenues: list | None, limite: int = LIMITE_PISTES) -> list:
    """Les pistes que l'explorateur garde, quatre au plus. Sans choix lisible : les quatre dernières testées."""
    if retenues:
        choix = [p for n, p in pistes_et_essais if n in retenues][:limite]
        if choix:
            return choix
    return [p for _, p in pistes_et_essais][-limite:]


def _pistes_pour_le_chef(pistes: list) -> list:
    return [{"famille": p["libelle_famille"], "piste": p["description"], "raison": p.get("raison"),
             "ordres": p.get("ordres"),
             "verdict": (p.get("verdict") or {}).get("libelle"),
             "angle_determinant": (p.get("angle_le_plus_faible") or {}).get("libelle"),
             "direction": (p.get("direction") or {}).get("libelle")} for p in pistes]


def repli(client, ordre: dict, simulation: dict, raison: str, mode: str = "ajuster") -> dict:
    """Sans explorateur : la taille compatible calculée par le code, présentée comme une piste."""
    from .inspection import extraire_pistes

    op = ordre.get("operation") or "comptant"
    if mode == "remplacer" or (op != "comptant" and not operations_avancees_permises(api.lire_fiche_client(client))):
        # Règles du code : pas de piste avancée pour un client débutant, et aucun montant ne répare une règle
        # stricte ; le repli ne montre alors aucune piste.
        avis = AVIS_REPLI_REMPLACER if mode == "remplacer" else AVIS_REPLI_SANS_PISTE
        return {"statut": "repli", "avis": avis, "raison_du_repli": raison, "intention": None, "cause_lue": None,
                "bilan": None, "cause": simulation.get("cause"), "pistes": [], "trace": [], "taille": None,
                "retour": {"statut": "repli", "avis": avis, "cause": simulation.get("cause"), "pistes": []}}
    taille = api.chercher_taille_compatible(client, ordre["ticker"], ordre["sens"], ordre["pourcentage"], op)
    trace = [{"etape": 0, "outil": "simuler_ordre", "arguments": {}, "resultat": simulation},
             {"etape": 0, "outil": "chercher_taille_compatible",
              "arguments": {"raison": "Calculée par le code : l'explorateur n'a pas pu finir."}, "resultat": taille}]
    pistes = [dict(p, etape=None) for p in extraire_pistes(trace, ordre["ticker"], ordre["sens"], ordre["pourcentage"])]
    return {"statut": "repli", "avis": AVIS_REPLI, "raison_du_repli": raison, "intention": None, "cause_lue": None,
            "bilan": None, "cause": simulation.get("cause"), "pistes": pistes, "trace": [], "taille": taille,
            "retour": {"statut": "repli", "avis": AVIS_REPLI, "cause": simulation.get("cause"),
                       "pistes": _pistes_pour_le_chef(pistes)}}


ESSAIS_SECOND_TOUR = 3          # essais de plus quand le chef de dossier renvoie le travail, une seule fois
TOURS_SECOND_TOUR = 3           # un tour d'essais en parallèle, un ajustement, le compte rendu


class Explorateur:
    """Un explorateur pour une analyse : un premier tour (`lancer`), puis au plus un second (`reprendre`) quand le chef
    de dossier renvoie le travail avec une critique. Le code borne tout : essais, tours, délai, un seul renvoi.

    `mode` : « ajuster » (ordre en tension) ou « remplacer » (ordre incompatible : seules les pistes qui remplacent
    l'instrument sont acceptées).
    """

    def __init__(self, client, ordre: dict, simulation: dict, modele=None, sur_etape=None, compteur=None,
                 mode: str = "ajuster", delai_s: float | None = None, sous_mandat: bool = False):
        self.client, self.ordre, self.simulation, self.modele = client, ordre, simulation, modele
        self.mode, self.delai_s, self.sous_mandat = mode, delai_s, sous_mandat
        self.registre: dict = {}
        self.bornes = {"n": 0, "limite": None}
        self.suivi = Suivi(sur_etape, agent="explorateur", ticker_ordre=ordre["ticker"], compteur=compteur,
                           complet=self._complet)
        self.agent, self.tours, self.renvois, self.dernier = None, [], 0, None

    def _complet(self, resultat):
        if isinstance(resultat, dict) and resultat.get("essai") in self.registre:
            return self.registre[resultat["essai"]]
        return resultat

    def _creer_agent(self):
        from strands import Agent, ModelRetryStrategy

        from .inspection import creer_modele, nom_modele
        from . import identifiants

        m = self.modele
        if m is None or isinstance(m, str):
            identifiants.charger_identifiants()
            # L'entrée de l'explorateur n'est faite que de faits écrits par le code et de la mission du chef de
            # dossier : le garde-fou Bedrock, qui y voyait parfois une demande de transaction, s'applique à ses
            # phrases montrées dans le rapport (voir `_bilan`), pas à cette entrée.
            from .inspection import EFFORT_EXPLORATEUR
            m = creer_modele(nom_modele(m), effort=EFFORT_EXPLORATEUR, garde_fou=False)
        avancees = operations_avancees_permises(api.lire_fiche_client(self.client))
        outils = creer_outils_explorateur(self.client, registre=self.registre, operations_avancees=avancees,
                                          mode=self.mode, ticker_ordre=self.ordre["ticker"], bornes=self.bornes)
        prompt = PROMPT_MANDAT if self.sous_mandat else PROMPT_EXPLORATEUR
        return Agent(model=m, tools=outils, system_prompt=prompt.read_text(encoding="utf-8"),
                     callback_handler=self.suivi.rappel, hooks=[self.suivi], name="explorateur",
                     retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=16))

    def _executer(self, message: str, delai_s: float | None = None, tours: int | None = None):
        """Un tour de travail dans un fil à part, borné par le délai ; lève DelaiDepasse ou l'erreur du modèle."""
        delai = delai_s if delai_s is not None else (DELAI_EXPLORATEUR_S if self.delai_s is None else self.delai_s)

        def travailler():
            if self.agent is None:
                self.agent = self._creer_agent()
            avant = len(self.agent.messages)
            r = self.agent(message, limits={"turns": tours or LIMITE_TOURS_EXPLORATEUR})
            return r, avant

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="explorateur")
        try:
            return pool.submit(travailler).result(timeout=delai)
        finally:
            pool.shutdown(wait=False)

    def lancer(self, mission) -> dict:
        """`mission` : le texte du chef de dossier, ou son mandat (dict : finalité supposée, cause, à respecter,
        pistes d'abord)."""
        self.mission = mission
        if isinstance(mission, dict):
            mission = "\n".join(f"- {cle.replace('_', ' ')} : {valeur}" for cle, valeur in mission.items() if valeur)
        return self._tour(entete(self.client, self.ordre, mission, self.simulation, mode=self.mode), 1)

    def reprendre(self, critique: str, delai_s: float | None = None) -> dict:
        """Le second et dernier tour : la critique du chef de dossier, au plus trois essais de plus."""
        if self.renvois >= 1:
            return {"erreur": "Le travail de l'explorateur a déjà été renvoyé une fois : rédige le rapport."}
        if self.dernier is None or self.dernier.get("statut") != "termine":
            return {"erreur": "L'explorateur n'a pas de travail à reprendre : rédige le rapport avec ce que tu as."}
        self.renvois += 1
        self.bornes["limite"] = self.bornes["n"] + ESSAIS_SECOND_TOUR
        message = ("Critique du chef de dossier sur tes pistes (simulation) :\n" + (critique or "(aucune précision)") +
                   f"\n\nFais au plus {ESSAIS_SECOND_TOUR} essais de plus pour y répondre, dans les mêmes règles, puis "
                   "rends un nouveau compte rendu en quatre lignes (les pistes retenues peuvent venir des deux tours).")
        precedent = self.dernier
        r = self._tour(message, 2, delai_s=delai_s, tours=TOURS_SECOND_TOUR)
        if r.get("statut") != "termine":    # le second tour a échoué : le premier compte rendu reste valable
            precedent = dict(precedent, avis_second_tour="Le second tour de l'explorateur n'a pas abouti.")
            self.dernier = precedent
            return precedent
        return r

    def _tour(self, message: str, numero: int, delai_s: float | None = None, tours: int | None = None) -> dict:
        from .inspection import extraire_trace, message_erreur, resume_etape, texte_final

        try:
            resultat, avant = self._executer(message, delai_s, tours)
        except DelaiDepasse:
            self.suivi.sur_etape = None     # l'explorateur abandonné ne parle plus à l'interface
            self.dernier = repli(self.client, self.ordre, self.simulation, "délai dépassé", self.mode)
            return self.dernier
        except Exception as e:
            self.dernier = repli(self.client, self.ordre, self.simulation, message_erreur(e), self.mode)
            return self.dernier
        try:
            nouvelles = extraire_trace(self.agent.messages[avant:], self.ordre["ticker"])
            for e in nouvelles:   # le résultat complet de chaque essai, pour la trace, les pistes et les contrôles
                plein = self._complet(e.get("resultat"))
                if plein is not e.get("resultat"):
                    e["resultat"] = plein
                    e["resultat_resume"] = resume_etape(e["outil"], e["arguments"], plein, self.ordre["ticker"])
                e["tour"] = numero
            self.tours.append(nouvelles)
            texte = texte_final(getattr(resultat, "message", None))
        except Exception as e:
            self.dernier = repli(self.client, self.ordre, self.simulation,
                                 f"compte rendu illisible ({type(e).__name__})", self.mode)
            return self.dernier
        self.dernier = self._bilan(texte)
        return self.dernier

    def trace(self) -> list:
        """Toutes les étapes de l'explorateur, numérotées dans son ordre (`etape`), avec leur `tour`."""
        etapes = [dict(e) for tour in self.tours for e in tour]
        for i, e in enumerate(etapes, start=1):
            e["etape"] = i
        return etapes

    def _bilan(self, texte: str | None) -> dict:
        from .inspection import extraire_pistes

        cr = lire_compte_rendu(texte)
        trace = self.trace()
        trace_complete = [{"etape": 0, "outil": "simuler_ordre", "arguments": {}, "resultat": self.simulation}] + trace
        essais = {e["etape"]: (e.get("resultat") or {}).get("essai") for e in trace if isinstance(e.get("resultat"), dict)}
        testees = extraire_pistes(trace_complete, self.ordre["ticker"], self.ordre["sens"], self.ordre["pourcentage"])
        pistes = retenir([(essais.get(p["etape"]), p) for p in testees], cr["retenues"])
        if not pistes and not cr["bilan"]:
            return repli(self.client, self.ordre, self.simulation, "aucune piste testée", self.mode)
        if self.modele is None or isinstance(self.modele, str):   # vrai Bedrock : ses phrases passent par le garde-fou
            from . import garde_fou as _garde_fou
            phrases = "\n".join(x for x in [cr["intention"], cr["cause"], cr["bilan"]] +
                                [p.get("raison") for p in pistes] if x)
            if _garde_fou.sortie_acceptee(phrases) is False:
                cr = {**cr, "intention": None, "cause": None, "bilan": None}
                pistes = [dict(p, raison=None) for p in pistes]
        return {"statut": "termine", "intention": cr["intention"], "cause_lue": cr["cause"], "bilan": cr["bilan"],
                "cause": self.simulation.get("cause"), "pistes": pistes, "nombre_essais": len(testees),
                "trace": trace, "compte_rendu": texte, "renvois": self.renvois,
                "retour": {"statut": "termine", "finalite_supposee": cr["intention"], "cause_lue": cr["cause"],
                           "bilan": cr["bilan"], "cause": self.simulation.get("cause"),
                           "pistes": _pistes_pour_le_chef(pistes)}}


def explorer(client, ordre: dict, mission: str, simulation: dict, modele=None, sur_etape=None, compteur=None,
             delai_s: float | None = None) -> dict:
    """Un seul tour d'exploration (comportement d'avant le chef de dossier qui juge les pistes)."""
    return Explorateur(client, ordre, simulation, modele, sur_etape, compteur, delai_s=delai_s).lancer(mission)
