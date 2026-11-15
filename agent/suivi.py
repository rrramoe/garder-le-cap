"""Suivi en direct d'une analyse : les étapes de l'agent envoyées à une fonction `sur_etape(evenement)`.

    Suivi(sur_etape, agent="principal")

Chaque événement est un dictionnaire qui porte `moment` et `agent` (le nom de l'agent au travail) :

- `debut_outil` : `etape`, `outil`, `arguments`, `libelle` (une phrase courte pour un débutant) ;
- `fin_outil` : `etape`, `outil`, `resultat_resume` (le même résumé que dans la trace) ;
- `redaction`, `verification`, `correction`, `fin` : sans autre champ.

Fils d'exécution : Strands fait tourner l'agent dans un fil à lui ; `debut_outil`, `fin_outil` et
`redaction` sont donc appelés depuis ce fil, pas depuis celui qui a appelé `inspecter`. `verification`,
`correction` et `fin` sont appelés depuis le fil de l'appelant. La fonction doit donc être sûre entre fils
(une `queue.Queue`, par exemple). Une fonction qui lève une exception ne casse jamais l'analyse : l'erreur
est ignorée. Un même `Suivi` s'accroche à n'importe quel agent Strands (`hooks=[suivi]`,
`callback_handler=suivi.rappel`), un sous-agent compris, avec son propre nom.
"""
from __future__ import annotations

import threading

from strands.hooks import (AfterToolCallEvent, BeforeModelCallEvent, BeforeToolCallEvent, HookProvider,
                           HookRegistry)


def _symbole(arguments: dict) -> str:
    return str((arguments or {}).get("ticker", "")).strip().upper()


def libelle_outil(outil: str, arguments: dict, ticker_ordre: str | None = None) -> str:
    """Phrase courte, en français simple, qui dit ce que l'agent fait."""
    a = arguments or {}
    symbole = _symbole(a)
    if outil == "lire_fiche_client":
        return "Je lis votre fiche."
    if outil == "lire_fiche_instrument":
        return f"Je lis la fiche de {symbole}." if symbole else "Je lis la fiche de l'instrument."
    if outil == "simuler_ordre":
        if ticker_ordre and symbole and symbole != ticker_ordre:
            return f"Je teste un ordre sur {symbole} à la place."
        return "Je simule l'ordre sur votre portefeuille."
    if outil == "chercher_taille_compatible":
        return "Je cherche un montant plus petit qui reste dans votre politique."
    if outil == "lister_instruments":
        return "Je regarde les autres instruments de la même classe."
    if outil == "simuler_scenario":
        return "Je teste une combinaison d'ordres."
    if outil == "expliquer_cause":
        return "Je cherche ce qui crée la tension."
    return "J'appelle un outil du moteur."


class Suivi(HookProvider):
    """Relaie les étapes d'un agent Strands à `sur_etape` ; ne lève jamais d'exception."""

    def __init__(self, sur_etape=None, agent: str = "principal", ticker_ordre: str | None = None):
        self.sur_etape, self.agent = sur_etape, agent
        self.ticker_ordre = str(ticker_ordre or "").strip().upper() or None
        self._etapes: dict = {}
        self._verrou = threading.Lock()
        self._redaction_annoncee = False

    def emettre(self, moment: str, **champs) -> None:
        if self.sur_etape is None:
            return
        try:
            self.sur_etape({"moment": moment, "agent": self.agent, **champs})
        except Exception:
            pass  # le suivi ne casse jamais l'analyse

    # --- Crochets Strands --------------------------------------------------------------------------

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeToolCallEvent, self._debut_outil)
        registry.add_callback(AfterToolCallEvent, self._fin_outil)
        registry.add_callback(BeforeModelCallEvent, self._appel_modele)

    def _etape(self, tool_use: dict) -> int:
        cle = tool_use.get("toolUseId") or id(tool_use)
        with self._verrou:
            if cle not in self._etapes:
                self._etapes[cle] = len(self._etapes) + 1
            return self._etapes[cle]

    def _debut_outil(self, event: BeforeToolCallEvent) -> None:
        try:
            tu = event.tool_use or {}
            outil, arguments = tu.get("name"), dict(tu.get("input") or {})
            self.emettre("debut_outil", etape=self._etape(tu), outil=outil, arguments=arguments,
                         libelle=libelle_outil(outil, arguments, self.ticker_ordre))
        except Exception:
            pass

    def _fin_outil(self, event: AfterToolCallEvent) -> None:
        try:
            from .inspection import _contenu_resultat, resume_etape

            tu = event.tool_use or {}
            outil = tu.get("name")
            resultat = _contenu_resultat(event.result)
            self.emettre("fin_outil", etape=self._etape(tu), outil=outil,
                         resultat_resume=resume_etape(outil, tu.get("input") or {}, resultat, self.ticker_ordre))
        except Exception:
            pass

    def _appel_modele(self, event: BeforeModelCallEvent) -> None:
        self._redaction_annoncee = False

    def rappel(self, **kwargs) -> None:
        """`callback_handler` Strands : annonce la rédaction au premier morceau de texte d'une réponse."""
        if kwargs.get("data") and not self._redaction_annoncee:
            self._redaction_annoncee = True
            self.emettre("redaction")
