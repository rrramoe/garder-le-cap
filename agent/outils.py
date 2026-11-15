"""Les cinq outils de l'agent : des enveloppes Strands autour de `moteur.api`.

Les outils sont créés pour une inspection et liés à son client. Le modèle passe un
`client_id` ; si c'est celui de l'inspection, l'outil utilise la fiche reçue, y compris
des réponses au questionnaire modifiées dans l'interface.
"""
from __future__ import annotations

from strands import tool

from moteur import api

NOMS_OUTILS = ("lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "chercher_taille_compatible",
               "lister_instruments")


def identifiant_client(client) -> str:
    """Identifiant que le modèle doit passer aux outils pour ce client."""
    if isinstance(client, str):
        return client.strip().lower()
    fiche = api.lire_fiche_client(client)
    if isinstance(fiche, dict) and fiche.get("id"):
        return str(fiche["id"]).strip().lower()
    if isinstance(client, dict):
        return str(client.get("persona") or client.get("id") or "personnalise").strip().lower()
    return "personnalise"


def creer_outils(client) -> list:
    """Crée les outils d'une inspection, liés au client (identifiant de persona ou fiche)."""
    id_lie = identifiant_client(client)

    def client_pour(client_id):
        if str(client_id).strip().lower() == id_lie:
            return client, None
        return None, {"erreur": f"Cette analyse porte sur le client « {id_lie} » : utilisez client_id=\"{id_lie}\"."}

    @tool(name="lire_fiche_client")
    def lire_fiche_client(client_id: str) -> dict:
        """Lit la fiche du client : questionnaire, profil, horizon, fourchettes, plafonds, contraintes strictes,
        préférences souples, niveau de détail et portefeuille, avec l'origine et la source de chaque élément.

        Args:
            client_id: Identifiant du client de l'analyse.
        """
        c, erreur = client_pour(client_id)
        return erreur or api.lire_fiche_client(c)

    @tool(name="lire_fiche_instrument")
    def lire_fiche_instrument(ticker: str) -> dict:
        """Lit la fiche d'un instrument : classe, devise, secteur, statistiques en CAD, étiquettes
        (valeur, règle, déclencheur, source ; une valeur peut être « indetermine ») et période des données.

        Args:
            ticker: Symbole de l'instrument, par exemple TSLA ou XIU.TO.
        """
        return api.lire_fiche_instrument(ticker)

    @tool(name="simuler_ordre")
    def simuler_ordre(client_id: str, ticker: str, sens: str, pourcentage: float, operation: str = "comptant") -> dict:
        """Simule l'ordre sur le portefeuille du client : contraintes strictes, notes avant et après,
        score, verdict (compatible, en_tension, incompatible), direction, et pour la marge ou le découvert
        le levier et le contrôle d'expérience (`operation`).

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument.
            sens: « achat » ou « vente ».
            pourcentage: Montant de l'ordre en % du portefeuille (15 = 15 %).
            operation: « comptant » (par défaut), « marge » (achat sur marge) ou « decouvert » (vente à découvert).
        """
        c, erreur = client_pour(client_id)
        return erreur or api.simuler_ordre(c, ticker, sens, pourcentage, operation)

    @tool(name="chercher_taille_compatible")
    def chercher_taille_compatible(client_id: str, ticker: str, sens: str, pourcentage: float,
                                   operation: str = "comptant") -> dict:
        """Cherche la plus grande taille d'ordre (pas de 0,5 %, jusqu'au montant demandé) dont le score
        atteint 50, avec la courbe du score selon la taille. Ne se lance pas si une contrainte stricte est violée.

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument.
            sens: « achat » ou « vente ».
            pourcentage: Montant demandé en % du portefeuille.
            operation: « comptant » (par défaut), « marge » ou « decouvert », comme pour simuler_ordre.
        """
        c, erreur = client_pour(client_id)
        return erreur or api.chercher_taille_compatible(c, ticker, sens, pourcentage, operation)

    @tool(name="lister_instruments")
    def lister_instruments(classe: str = "toutes") -> dict:
        """Liste les instruments de l'univers, filtrés par classe de la politique.

        Args:
            classe: liquidites, revenu_fixe, actions, alternatifs, ou toutes.
        """
        return api.lister_instruments(classe)

    return [lire_fiche_client, lire_fiche_instrument, simuler_ordre, chercher_taille_compatible, lister_instruments]
