"""Construit `reference/fiches_instruments.json` (cache versionné des fiches d'instruments).

Usage : python scripts/construire_fiches.py [--sans-reseau]

- Statistiques en CAD calculées par le moteur sur `data/prices_daily.csv`.
- Date de première cotation : `firstTradeDate` de yfinance (accès réseau), pour les
  actions individuelles. Avec `--sans-reseau`, les dates déjà présentes dans le cache
  sont réutilisées ; sinon l'étiquette `etablie` est `indetermine`.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from moteur import donnees, etiquettes, references  # noqa: E402

SORTIE = RACINE / "reference" / "fiches_instruments.json"


def premiere_cotation_yfinance(ticker: str) -> str | None:
    import yfinance as yf

    try:
        meta = yf.Ticker(ticker).get_history_metadata()
        valeur = meta.get("firstTradeDate")
        if valeur is None:
            return None
        return str(valeur)[:10]
    except Exception:
        return None


def main() -> None:
    sans_reseau = "--sans-reseau" in sys.argv
    ancien = {}
    if SORTIE.exists():
        ancien = json.loads(SORTIE.read_text(encoding="utf-8")).get("instruments", {})

    univ = donnees.univers()
    vol_spy = donnees.statistiques({"SPY": 1.0})["volatilite_annualisee"]
    aujourd_hui = date.today().isoformat()
    fiches = {}
    for ticker, ligne in univ.iterrows():
        stats = donnees.statistiques({ticker: 1.0})
        classe_actif = ligne["asset_class"]
        spec = etiquettes.etiquette_speculatif(stats["volatilite_annualisee"], vol_spy)

        premiere, recupere_le = None, None
        if classe_actif == "equity":
            if sans_reseau:
                prec = ancien.get(ticker, {}).get("premiere_cotation", {})
                premiere, recupere_le = prec.get("date"), prec.get("recupere_le")
            else:
                premiere = premiere_cotation_yfinance(ticker)
                recupere_le = aujourd_hui if premiere else None

        fiches[ticker] = {
            "symbole": ticker,
            "nom": ligne["name"],
            "classe_actif": classe_actif,
            "classe_politique": references.classe_politique(ticker),
            "secteur": ligne["sector"],
            "marche": ligne["market"],
            "devise": ligne["currency"],
            "statistiques_cad": {
                "volatilite_annualisee": round(stats["volatilite_annualisee"], 6),
                "pire_baisse": round(stats["pire_baisse"], 6),
                "temps_sous_l_eau_annees": round(stats["temps_sous_l_eau_annees"], 4),
                "temps_sous_l_eau_debut": stats["temps_sous_l_eau_debut"],
                "temps_sous_l_eau_fin": stats["temps_sous_l_eau_fin"],
                "non_recupere": stats["non_recupere"],
            },
            "premiere_cotation": {"date": premiere, "recupere_le": recupere_le, "source": "yfinance_first_trade_date"}
            if classe_actif == "equity" else None,
            "etiquettes": {
                "speculatif": spec,
                "etablie": etiquettes.etiquette_etablie(classe_actif, spec["valeur"], premiere, recupere_le),
                "crypto": etiquettes.etiquette_crypto(classe_actif),
                "techno": etiquettes.etiquette_techno(classe_actif, ligne["sector"]),
                "ecarte_esg": etiquettes.etiquette_ecarte_esg(ticker, classe_actif),
            },
        }

    sortie = {
        "genere_le": aujourd_hui,
        "periode": donnees.periode(),
        "volatilite_spy_cad": round(vol_spy, 6),
        "seuil_speculatif": round(2 * vol_spy, 6),
        "instruments": fiches,
    }
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec = [t for t, f in fiches.items() if f["etiquettes"]["speculatif"]["valeur"] is True]
    etab = {t: f["etiquettes"]["etablie"]["valeur"] for t, f in fiches.items() if f["classe_actif"] == "equity"}
    print(f"{len(fiches)} fiches écrites dans {SORTIE.relative_to(RACINE)}")
    print("Spéculatifs :", ", ".join(spec))
    print("Établie :", etab)


if __name__ == "__main__":
    main()
