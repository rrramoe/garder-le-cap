"""Profils des instruments hors des données des organisateurs (fiche du titre, partie B).

    python scripts/profils_instruments.py

Source : Yahoo Finance par la bibliothèque `yfinance` (la source des organisateurs pour les prix). Aucune
coordonnée personnelle n'est envoyée. Conditions de Yahoo : les données téléchargées ne sont pas publiées
dans le dépôt. Le script écrit :

- `data/profils_bruts/<ticker>.json` : le téléchargement brut (ignoré par git) ;
- `reference/profils_instruments.json` : le profil compact lu par le moteur (ignoré par git, déposé dans le
  bucket S3 privé par `python scripts/creer_bucket.py`).

Entreprise : une phrase factuelle composée par le script à partir des champs (industrie, pays, effectif),
pas la description de Yahoo ; capitalisation, chiffre d'affaires, bénéfice net, dette, encaisse ; signe des
trois flux de trésorerie du dernier exercice. Fonds : dix plus grandes positions et leur poids, répartition
par secteur et par type d'actif, ratio des frais. Une valeur absente vaut « indetermine ».
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

BRUTS = RACINE / "data" / "profils_bruts"
SORTIE = RACINE / "reference" / "profils_instruments.json"
INDET = "indetermine"
FLUX = {"exploitation": "Operating Cash Flow", "investissement": "Investing Cash Flow", "financement": "Financing Cash Flow"}


def _nombre(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return INDET
    return INDET if x != x else x


def _signe(x):
    x = _nombre(x)
    return INDET if x == INDET else ("positif" if x > 0 else "negatif" if x < 0 else "nul")


def phrase_entreprise(nom: str, info: dict) -> str:
    morceaux = [f"{nom} est une entreprise"]
    if info.get("industry"):
        morceaux.append(f"de l'industrie « {info['industry']} »")
    if info.get("country"):
        morceaux.append(f"dont le siège est situé dans ce pays : {info['country']}")
    phrase = " ".join(morceaux) + "."
    if info.get("fullTimeEmployees"):
        phrase += f" Elle compte environ {int(info['fullTimeEmployees']):,} employés à temps plein.".replace(",", " ")
    return phrase


def profil_entreprise(t, nom: str, info: dict) -> tuple[dict, dict]:
    brut_flux = {}
    flux = {}
    try:
        cf = t.cashflow
        col = cf.columns[0]
        for cle, ligne in FLUX.items():
            v = cf.loc[ligne, col] if ligne in cf.index else None
            brut_flux[cle] = _nombre(v)
            flux[cle] = _signe(v)
        exercice = str(col)[:10]
    except Exception:
        flux = {k: INDET for k in FLUX}
        exercice = INDET
    return {
        "type": "entreprise",
        "description": phrase_entreprise(nom, info),
        "industrie": info.get("industry") or INDET,
        "pays": info.get("country") or INDET,
        "devise_capitalisation": info.get("currency") or INDET,
        "devise_des_etats_financiers": info.get("financialCurrency") or INDET,
        "capitalisation": _nombre(info.get("marketCap")),
        "chiffre_affaires": _nombre(info.get("totalRevenue")),
        "benefice_net": _nombre(info.get("netIncomeToCommon")),
        "dette": _nombre(info.get("totalDebt")),
        "encaisse": _nombre(info.get("totalCash")),
        "flux_tresorerie_signes": flux,
        "exercice_flux": exercice,
    }, brut_flux


def profil_fonds(t, info: dict) -> tuple[dict, dict]:
    brut = {}
    try:
        fd = t.funds_data
        top = fd.top_holdings
        positions = [{"symbole": str(s), "nom": str(r["Name"]), "poids": round(float(r["Holding Percent"]), 6)}
                     for s, r in top.head(10).iterrows()]
        secteurs = {k: round(float(v), 6) for k, v in (fd.sector_weightings or {}).items()}
        types = {k: round(float(v), 6) for k, v in (fd.asset_classes or {}).items()}
        brut = {"top_holdings": positions, "sector_weightings": secteurs, "asset_classes": types}
    except Exception:
        positions, secteurs, types = [], {}, {}
    frais = _nombre(info.get("netExpenseRatio"))
    return {
        "type": "fonds",
        "description": (f"Fonds négocié en bourse, catégorie « {info['category']} »." if info.get("category")
                        else "Fonds négocié en bourse."),
        "famille": info.get("fundFamily") or INDET,
        "dix_plus_grandes_positions": positions or INDET,
        "secteurs": secteurs or INDET,
        "types_actifs": types or INDET,
        "ratio_frais_pct": frais,
        "actif_total": _nombre(info.get("totalAssets")),
    }, brut


def main() -> None:
    import pandas as pd
    import yfinance as yf

    univers = pd.read_csv(RACINE / "data" / "assets_universe.csv").set_index("ticker")
    BRUTS.mkdir(parents=True, exist_ok=True)
    aujourd_hui = date.today().isoformat()
    profils, echecs = {}, []
    for ticker, ligne in univers.iterrows():
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
        except Exception as e:
            echecs.append(f"{ticker} ({type(e).__name__})")
            profils[ticker] = {"type": INDET, "recupere_le": None, "source": "yfinance_profils"}
            continue
        if ligne["asset_class"] == "equity":
            p, extra = profil_entreprise(t, ligne["name"], info)
        elif str(ligne["asset_class"]).startswith("etf"):
            p, extra = profil_fonds(t, info)
        else:
            p, extra = {"type": "cryptoactif", "description": f"{ligne['name']} est un cryptoactif, sans entreprise ni "
                                                             "fonds derrière lui : pas d'états financiers."}, {}
        p.update(recupere_le=aujourd_hui, source="yfinance_profils")
        profils[ticker] = p
        (BRUTS / f"{ticker}.json").write_text(json.dumps({"info": info, **extra}, ensure_ascii=False, default=str),
                                              encoding="utf-8")
    SORTIE.write_text(json.dumps({"genere_le": aujourd_hui, "source": "yfinance_profils", "profils": profils},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(profils)} profils écrits dans {SORTIE.relative_to(RACINE)} (non publié ; bucket : scripts/creer_bucket.py)")
    if echecs:
        print("Échecs :", ", ".join(echecs))


if __name__ == "__main__":
    main()
