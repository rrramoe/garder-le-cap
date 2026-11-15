"""Les six outils de l'agent : des enveloppes Strands autour de `moteur.api`.

Les outils sont créés pour une inspection et liés à son client. Le modèle passe un
`client_id` ; si c'est celui de l'inspection, l'outil utilise la fiche reçue, y compris
des réponses au questionnaire modifiées dans l'interface.
"""
from __future__ import annotations

from strands import tool

from moteur import api

NOMS_OUTILS = ("lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "chercher_taille_compatible",
               "lister_instruments", "simuler_scenario")


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

    @tool(name="simuler_scenario")
    def simuler_scenario(client_id: str, ordres: list[dict]) -> dict:
        """Simule plusieurs ordres appliqués ensemble (1 à 4), par exemple un achat partagé entre l'instrument et
        un fonds diversifié, ou un achat payé par la vente d'une autre position. Les ventes sont versées à
        l'encaisse et paient les achats ; leur total ne peut pas dépasser celui des achats. Même résultat que
        simuler_ordre (verdict, score, direction, cause), plus la liste `ordres`.

        Args:
            client_id: Identifiant du client de l'analyse.
            ordres: Liste de 1 à 4 ordres {"ticker": ..., "sens": "achat" ou "vente", "pourcentage": ...}
                (et "operation" si besoin), en % du portefeuille.
        """
        c, erreur = client_pour(client_id)
        return erreur or api.simuler_scenario(c, ordres)

    return [lire_fiche_client, lire_fiche_instrument, simuler_ordre, chercher_taille_compatible, lister_instruments,
            simuler_scenario]


NOM_OUTIL_APPORT = "decrire_apport"


def creer_outil_decrire_apport(client):
    """Outil descriptif pour l'agent explorateur, lié au client de l'analyse (comme les autres outils)."""
    id_lie = identifiant_client(client)

    @tool(name=NOM_OUTIL_APPORT)
    def decrire_apport(client_id: str, ticker: str, pourcentage: float | None = None) -> dict:
        """Décrit ce qu'un instrument apporterait au portefeuille du client, avec des faits seulement
        (aucune note, aucun verdict) : corrélation avec le portefeuille actuel, les trois positions les plus
        proches, l'exposition actuelle à sa classe, à son secteur et à ses étiquettes (avec la limite de la
        politique quand il y en a une), la part du portefeuille et du risque après un achat de `pourcentage` %,
        et les instruments de la même classe classés du plus proche au plus éloigné (volatilité, pire baisse,
        étiquettes), pour choisir un complément ou un substitut sur preuves.

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument, par exemple TSLA.
            pourcentage: Facultatif. Achat envisagé en % du portefeuille (15 = 15 %).
        """
        if str(client_id).strip().lower() != id_lie:
            return {"erreur": f"Cette analyse porte sur le client « {id_lie} » : utilisez client_id=\"{id_lie}\"."}
        return api.decrire_apport(client, ticker, pourcentage)

    return decrire_apport


# --- Équipe de deux agents -----------------------------------------------------------------------

NOMS_OUTILS_PRINCIPAL = ("lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "envoyer_explorateur")
NOMS_OUTILS_EXPLORATEUR = ("lire_fiche_client", "lire_fiche_instrument", NOM_OUTIL_APPORT, "lister_instruments",
                           "simuler_ordre", "simuler_scenario", "chercher_taille_compatible")
LIMITE_PISTES = 4     # pistes rendues au chef de dossier, au plus
LIMITE_ESSAIS = 6     # essais de l'explorateur, au plus (il en garde quatre)


def creer_outils_principal(client, envoyer) -> list:
    """Outils du chef de dossier : les trois lectures et `envoyer_explorateur`.

    `envoyer(mission)` est fourni par l'analyse : il vérifie les règles (ordre en tension, un seul envoi), fait
    travailler l'explorateur et renvoie son compte rendu, ou `{"erreur": ...}`.
    """
    communs = {t.tool_name: t for t in creer_outils(client)}
    id_lie = identifiant_client(client)

    @tool(name="envoyer_explorateur")
    def envoyer_explorateur(client_id: str, mission: str) -> dict:
        """Envoie l'agent explorateur chercher des pistes pour un ordre « en tension » (refusé sinon, et une seule
        fois par analyse). Il renvoie son hypothèse sur ce que l'ordre apporte, la cause, et 2 à 4 pistes testées
        par le moteur, chacune avec sa raison et son résultat (verdict, score, direction).

        Args:
            client_id: Identifiant du client de l'analyse.
            mission: Ta lecture du cas en 2 ou 3 phrases : la règle en cause, ce que ce client cherche, évite ou
                exclut, et ce que l'ordre semble viser.
        """
        if str(client_id).strip().lower() != id_lie:
            return {"erreur": f"Cette analyse porte sur le client « {id_lie} » : utilisez client_id=\"{id_lie}\"."}
        return envoyer(str(mission or "").strip())

    return [communs["lire_fiche_client"], communs["lire_fiche_instrument"], communs["simuler_ordre"],
            envoyer_explorateur]


def compacter_simulation(r: dict) -> dict:
    """Ce dont l'explorateur a besoin pour décider de l'essai suivant ; le résultat complet reste dans la trace."""
    if not isinstance(r, dict) or "erreur" in r:
        return r
    cause = {k: v for k, v in (r.get("cause") or {}).items() if k != "autres_mesures_sous_le_seuil"}
    return {"verdict": (r.get("verdict") or {}).get("code"), "score": r.get("score"),
            "direction": (r.get("direction") or {}).get("cas"), "cause": cause,
            "solidite": (r.get("solidite") or {}).get("statut"),
            "contraintes_violees": (r.get("contraintes_strictes") or {}).get("themes_violes"),
            "portefeuille_apres_pct": r.get("portefeuille_apres_pct")}


def compacter_taille(r: dict) -> dict:
    if not isinstance(r, dict) or "erreur" in r:
        return r
    taille = r.get("taille_compatible_pct")
    point = next((p for p in r.get("courbe") or [] if p.get("taille_pct") == taille), None)
    meilleur = max(r.get("courbe") or [{}], key=lambda p: p.get("score", -1))
    return {"lancee": r.get("lancee", True), "raison": r.get("raison"), "taille_compatible_pct": taille,
            "taille_demandee_pct": r.get("taille_demandee_pct"), "issue": r.get("issue"),
            "score_a_cette_taille": (point or {}).get("score"),
            "meilleur_point": {k: meilleur.get(k) for k in ("taille_pct", "score", "mesure_min")}}


def compacter_apport(r: dict, candidats: int = 8) -> dict:
    """`decrire_apport` sans libellés, périodes ni sources, et ses candidats les plus proches seulement."""
    if not isinstance(r, dict) or "erreur" in r:
        return r

    def nettoyer(x):
        if isinstance(x, dict):
            return {k: nettoyer(v) for k, v in x.items() if k not in ("libelle", "periode", "sources", "nom")}
        if isinstance(x, list):
            return [nettoyer(v) for v in x]
        return x
    c = nettoyer({k: v for k, v in r.items() if k not in ("candidats", "sources", "periode", "frequence")})
    c["candidats"] = [{**{k: v for k, v in x.items() if k not in ("etiquettes", "nom")},
                       "etiquettes_vraies": [e for e, v in (x.get("etiquettes") or {}).items() if v is True]}
                      for x in (r.get("candidats") or [])[:candidats]]
    return c


def creer_outils_explorateur(client, limite_essais: int = LIMITE_ESSAIS, registre: dict | None = None) -> list:
    """Outils de l'explorateur. Chaque essai porte sa `raison` et reçoit un numéro (`essai`) ; le code borne les
    essais à `limite_essais`. L'explorateur reçoit un résultat compact ; le résultat complet de chaque essai va dans
    `registre` (numéro d'essai → résultat), pour la trace et le rapport."""
    id_lie = identifiant_client(client)
    essais = {"n": 0}
    registre = {} if registre is None else registre

    def verifier(client_id):
        if str(client_id).strip().lower() != id_lie:
            return {"erreur": f"Cette analyse porte sur le client « {id_lie} » : utilisez client_id=\"{id_lie}\"."}
        if essais["n"] >= limite_essais:
            return {"erreur": f"Limite de {limite_essais} essais atteinte : rends ton compte rendu."}
        return None

    def numeroter(resultat: dict, compacter=compacter_simulation) -> dict:
        if isinstance(resultat, dict) and "erreur" not in resultat:
            essais["n"] += 1
            registre[essais["n"]] = {"essai": essais["n"], **resultat}
            return {"essai": essais["n"], **compacter(resultat)}
        return resultat

    communs = {t.tool_name: t for t in creer_outils(client)}

    @tool(name="simuler_ordre")
    def simuler_ordre(client_id: str, ticker: str, sens: str, pourcentage: float, raison: str,
                      operation: str = "comptant") -> dict:
        """Teste une piste d'un seul ordre (un autre instrument, ou un autre montant) : verdict, score, direction,
        cause. Compte dans la limite de six essais.

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument.
            sens: « achat » ou « vente ».
            pourcentage: Montant en % du portefeuille.
            raison: Une phrase : ce que la piste garde de la finalité supposée, et comment elle répond à la cause.
            operation: « comptant » (par défaut), « marge » ou « decouvert ».
        """
        return verifier(client_id) or numeroter(api.simuler_ordre(client, ticker, sens, pourcentage, operation))

    @tool(name="simuler_scenario")
    def simuler_scenario(client_id: str, ordres: list[dict], raison: str) -> dict:
        """Teste une piste de plusieurs ordres appliqués ensemble (1 à 4), seule ou en combinaison : un achat
        partagé entre l'instrument et un fonds diversifié, un montant plus petit plus un complément, un achat payé
        en partie par la vente d'une autre position. Les ventes sont versées à l'encaisse et ne peuvent pas dépasser
        le total des achats. Compte dans la limite de six essais.

        Args:
            client_id: Identifiant du client de l'analyse.
            ordres: Liste d'ordres {"ticker": ..., "sens": "achat" ou "vente", "pourcentage": ...}.
            raison: Une phrase : ce que la piste garde de la finalité supposée, et comment elle répond à la cause.
        """
        return verifier(client_id) or numeroter(api.simuler_scenario(client, ordres))

    @tool(name="chercher_taille_compatible")
    def chercher_taille_compatible(client_id: str, ticker: str, sens: str, pourcentage: float, raison: str,
                                   operation: str = "comptant") -> dict:
        """Teste la piste d'un montant plus petit : la plus grande taille (pas de 0,5 %, jusqu'au montant demandé)
        dont le score atteint 50, avec la courbe. Compte dans la limite de six essais.

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument.
            sens: « achat » ou « vente ».
            pourcentage: Montant demandé en % du portefeuille.
            raison: Une phrase : pourquoi cette piste répond à la cause.
            operation: « comptant » (par défaut), « marge » ou « decouvert ».
        """
        return verifier(client_id) or numeroter(api.chercher_taille_compatible(client, ticker, sens, pourcentage,
                                                                              operation), compacter_taille)

    apport = creer_outil_decrire_apport(client)

    @tool(name=NOM_OUTIL_APPORT)
    def decrire_apport(client_id: str, ticker: str, pourcentage: float | None = None) -> dict:
        """Décrit ce qu'un autre instrument apporterait au portefeuille (faits seulement, aucune note) : corrélations,
        exposition actuelle à sa classe, son secteur et ses étiquettes, part du risque après l'achat, et les
        candidats de la même classe classés du plus proche au plus éloigné. Celui de l'ordre t'est déjà donné.

        Args:
            client_id: Identifiant du client de l'analyse.
            ticker: Symbole de l'instrument.
            pourcentage: Facultatif. Achat envisagé en % du portefeuille.
        """
        return compacter_apport(apport._tool_func(client_id, ticker, pourcentage))

    return [communs["lire_fiche_client"], communs["lire_fiche_instrument"], decrire_apport,
            communs["lister_instruments"], simuler_ordre, simuler_scenario, chercher_taille_compatible]
