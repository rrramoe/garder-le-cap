"""Preuves, sur le vrai Bedrock, que chaque agent de l'équipe mérite sa place (docs/agents.md).

    python scripts/preuves_equipe.py [fichier.json]

1. Même ordre, deux fiches qui ne diffèrent que par leurs thèmes : pistes différentes.
2. Deux ordres en tension aux causes différentes : familles de pistes différentes.
3. Même ordre, expérience « débutante » ou « avancée » : explications différentes, reliées à l'objectif ou à l'horizon.
4. Test 6 adapté : le cas 2 (Mateo, XOM) n'envoie pas l'explorateur.
5. Le cas du propriétaire : une débutante qui veut préserver son capital vend à découvert. Le verdict vient des notes
   mesurées, l'explication nomme la contradiction avec l'objectif déclaré, aucune piste n'utilise une opération
   avancée. Le même ordre pour une fiche « avancée », « croissance à long terme » : aucune contradiction nommée.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import inspection  # noqa: E402

CAS = {
    "robert_tsla": ("robert", "TSLA", "achat", 15),
    "robert_tsla_techno_exclue": ({"persona": "robert", "questionnaire": {"themes": {"techno": "exclure"}}},
                                  "TSLA", "achat", 15),
    "robert_ry": ("robert", "RY.TO", "achat", 15),
    "robert_btc": ("robert", "BTC-USD", "achat", 5),
    "robert_tsla_debutante": ({"persona": "robert", "questionnaire": {"experience": "debutante"}}, "TSLA", "achat", 15),
    "mateo_xom": ("mateo", "XOM", "achat", 8),
    "decouvert_debutante": ({"persona": "robert", "questionnaire": {"experience": "debutante",
                                                                    "objectif": "preserver_capital"}},
                            "TSLA", "vente", 10, "decouvert"),
    # Fiche « avancée », « croissance à long terme », portefeuille d'actions dans sa politique (hors personas).
    "decouvert_avancee": ({"id": "sam", "nom": "Sam", "questionnaire": {
        "experience": "avancee", "objectif": "croissance_long_terme", "horizon": "15_plus", "fluctuations": "elevees",
        "themes": {}}, "portefeuille_pct": {"ZST.TO": 8, "XBB.TO": 8, "SPY": 30, "XIU.TO": 22, "QQQ": 12, "MSFT": 5,
                                             "CNR.TO": 5, "GLD": 10}},
                          "TSLA", "vente", 10, "decouvert"),
}
# 6. Un client qui n'est aucun des trois personas, et un instrument hors des ordres de démonstration.
CAS["lea_shop"] = ({"id": "lea", "nom": "Léa", "questionnaire": {
    "objectif": "revenu_regulier", "horizon": "5_8", "fluctuations": "moderees", "experience": "intermediaire",
    "themes": {"ecarte_esg": "eviter", "crypto": "exclure"}},
    "portefeuille_pct": {"ZST.TO": 12, "XBB.TO": 25, "AGG": 10, "XIU.TO": 15, "SPY": 15, "ENB.TO": 8, "JPM": 5,
                         "GLD": 10}}, "SHOP.TO", "achat", 8)
CONTRADICTION = ("contre votre objectif", "peu cohérent", "pas cohérent avec", "contredit", "contradiction", "va à l'encontre", "en opposition",
                 "s'oppose", "pas cohérent", "incohéren", "contraire")


def resume(r: dict) -> dict:
    return {"duree_s": r["duree_s"], "erreur": r["erreur"],
            "verdict": next((e["resultat"].get("verdict", {}).get("code") for e in r["trace"]
                             if e["outil"] == "simuler_ordre" and isinstance(e.get("resultat"), dict)), None),
            "ordres_des_pistes": [o for p in r["pistes"] for o in p["ordres"]],
            "outils": [f"{e['agent']}:{e['outil']}" for e in r["trace"]],
            "finalite_supposee": r["intention"],
            "pistes": [{"famille": p["famille"], "piste": p["description"], "verdict": p["verdict"]["code"],
                        "score": p["score"], "raison": p["raison"]} for p in r["pistes"]],
            "explorateur": next(({"statut": a.get("statut"), "avis": a.get("avis"),
                                  "raison_du_repli": a.get("raison_du_repli")} for a in r["agents"]
                                 if a["nom"] == "explorateur"), None),
            "ancrage": r["ancrage"].get("statut"), "correction": r.get("correction"),
            "explication": r["explication"]}


def main() -> int:
    with ThreadPoolExecutor(max_workers=4) as pool:
        resultats = dict(zip(CAS, pool.map(lambda args: resume(inspection.inspecter(
            *args[:4], operation=args[4] if len(args) > 4 else "comptant")), CAS.values())))
    sortie = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if sortie:
        sortie.write_text(json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")
    for nom, r in resultats.items():
        print(f"== {nom} ({r['duree_s']} s){' ERREUR ' + r['erreur'] if r['erreur'] else ''}")
        print("   étapes :", ", ".join(r["outils"]))
        print("   finalité supposée :", r["finalite_supposee"])
        for p in r["pistes"]:
            print(f"   - [{p['famille']}] {p['piste']} : {p['verdict']} ({p['score']})")
    familles = {n: sorted({p["famille"] for p in r["pistes"]}) for n, r in resultats.items()}
    pistes = {n: [p["piste"] for p in r["pistes"]] for n, r in resultats.items()}
    print("\n1. Thèmes différents, pistes différentes :", pistes["robert_tsla"] != pistes["robert_tsla_techno_exclue"])
    print("2. Causes différentes (TSLA risque, RY.TO plafond, BTC-USD crypto), familles :", familles["robert_tsla"],
          familles["robert_ry"], familles["robert_btc"])
    print("3. Débutante et avancée, explications différentes :",
          resultats["robert_tsla"]["explication"] != resultats["robert_tsla_debutante"]["explication"])
    print("4. Mateo XOM sans explorateur :", not any("envoyer_explorateur" in o for o in resultats["mateo_xom"]["outils"]))
    deb, ava = resultats["decouvert_debutante"], resultats["decouvert_avancee"]
    print("5. Vente à découvert : verdicts du moteur (débutante, avancée) :", deb["verdict"], ava["verdict"])
    print("   contradiction nommée (débutante, avancée) :",
          any(m in (deb["explication"] or "").lower() for m in CONTRADICTION),
          any(m in (ava["explication"] or "").lower() for m in CONTRADICTION))
    lea = resultats["lea_shop"]
    print("6. Léa (hors personas), SHOP.TO : explorateur", (lea["explorateur"] or {}).get("statut"), "| pistes :",
          [p["piste"] for p in lea["pistes"]])
    print("   pistes de la débutante sans opération avancée :",
          all(o.get("operation", "comptant") == "comptant" for o in deb["ordres_des_pistes"]),
          [p["piste"] for p in deb["pistes"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
