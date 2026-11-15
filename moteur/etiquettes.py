"""Étiquettes des instruments (section 6 de la spécification).

Chaque étiquette vaut `true`, `false`, `"indetermine"` ou `"sans_objet"`, avec la
règle appliquée, le chiffre qui l'a déclenchée et sa source.
"""
from __future__ import annotations

from datetime import date

from . import references

DATE_REFERENCE = date(2026, 11, 12)  # fin des données
ANNEES_ETABLIE = 20
MULTIPLE_SPECULATIF = 2.0
SECTEUR_TECHNO = "Information Technology"

VRAI, FAUX, INDETERMINE, SANS_OBJET = True, False, "indetermine", "sans_objet"


def _est_action_individuelle(classe_actif: str) -> bool:
    return classe_actif == "equity"


def etiquette_speculatif(vol: float, vol_spy: float) -> dict:
    seuil = MULTIPLE_SPECULATIF * vol_spy
    return {
        "valeur": bool(vol > seuil),
        "regle": "Volatilité annualisée en CAD > 2 x celle de SPY en CAD.",
        "declencheur": {"volatilite_annualisee_cad": round(vol, 4), "volatilite_spy_cad": round(vol_spy, 4), "seuil": round(seuil, 4)},
        "source": "hypothese_etiquettes",
    }


def etiquette_etablie(classe_actif: str, speculatif: bool, premiere_cotation: str | None, recupere_le: str | None) -> dict:
    regle = "Première cotation il y a au moins 20 ans (au 2026-11-12) et non spéculatif. Actions individuelles seulement."
    if not _est_action_individuelle(classe_actif):
        return {"valeur": SANS_OBJET, "regle": regle, "declencheur": None, "source": "hypothese_etiquettes"}
    if not premiere_cotation:
        return {
            "valeur": INDETERMINE, "regle": regle,
            "declencheur": {"premiere_cotation": None, "remarque": "firstTradeDate absent de yfinance."},
            "source": "yfinance_first_trade_date",
        }
    d = date.fromisoformat(premiere_cotation[:10])
    age = (DATE_REFERENCE - d).days / 365.25
    valeur = bool(age >= ANNEES_ETABLIE and not speculatif)
    return {
        "valeur": valeur, "regle": regle,
        "declencheur": {"premiere_cotation": premiere_cotation[:10], "anciennete_annees": round(age, 1),
                        "speculatif": speculatif, "recupere_le": recupere_le},
        "source": "yfinance_first_trade_date",
    }


def etiquette_crypto(classe_actif: str) -> dict:
    return {
        "valeur": classe_actif == "crypto",
        "regle": "Classe d'actifs crypto.",
        "declencheur": {"classe_actif": classe_actif},
        "source": "donnees_marche",
    }


def etiquette_techno(classe_actif: str, secteur: str) -> dict:
    regle = "Secteur « Information Technology ». Actions individuelles seulement."
    if not _est_action_individuelle(classe_actif):
        return {"valeur": SANS_OBJET, "regle": regle, "declencheur": {"secteur": secteur}, "source": "donnees_marche"}
    return {"valeur": secteur == SECTEUR_TECHNO, "regle": regle, "declencheur": {"secteur": secteur}, "source": "donnees_marche"}


def etiquette_ecarte_esg(ticker: str, classe_actif: str) -> dict:
    ref = references.charger("statut_esg")
    regle = "Statut dans le tableau ESG (méthode FTSE Global Choice, fonds ESGV et VSGX). Actions individuelles seulement."
    if not _est_action_individuelle(classe_actif):
        return {"valeur": SANS_OBJET, "regle": regle, "declencheur": {"statut": "sans_objet"}, "source": "vanguard_esgv_2026"}
    entree = ref["statuts"].get(ticker, {"statut": "indetermine", "preuve": "Non vérifié."})
    statut = entree["statut"]
    valeur = {"ecarte": VRAI, "ecarte_deduit": VRAI, "retenu": FAUX}.get(statut, INDETERMINE)
    source = {"ecarte_deduit": "hypothese_esg_deduit"}.get(statut, "vanguard_vsgx_2026" if ticker.endswith(".TO") else "vanguard_esgv_2026")
    return {"valeur": valeur, "regle": regle, "declencheur": {"statut": statut, "preuve": entree["preuve"]}, "source": source}


def etiquette_dividende(revenu: dict) -> dict:
    regle = "A versé au moins un dividende dans les 12 derniers mois des données (corporate_actions.csv)."
    d12 = revenu.get("dividendes_12_mois") if isinstance(revenu, dict) else None
    if not isinstance(d12, (int, float)):
        return {"valeur": INDETERMINE, "regle": regle, "declencheur": {"dividendes_12_mois": None},
                "source": "donnees_dividendes"}
    return {"valeur": bool(d12 > 0), "regle": regle,
            "declencheur": {"dividendes_12_mois": d12, "devise": revenu.get("devise")}, "source": "donnees_dividendes"}


def etiquette_devise_etrangere(devise: str) -> dict:
    return {"valeur": devise != "CAD", "regle": "Coté dans une autre devise que le dollar canadien.",
            "declencheur": {"devise": devise}, "source": "donnees_marche"}


def etiquette_action_individuelle(classe_actif: str) -> dict:
    return {"valeur": _est_action_individuelle(classe_actif),
            "regle": "Action d'une seule entreprise (classe « equity »), par opposition à un fonds ou à un cryptoactif.",
            "declencheur": {"classe_actif": classe_actif}, "source": "donnees_marche"}
