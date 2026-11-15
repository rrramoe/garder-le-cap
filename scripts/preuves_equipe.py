"""Preuves, sur le vrai Bedrock, que chaque agent de l'équipe mérite sa place (docs/agents.md).

    python scripts/preuves_equipe.py [fichier.json]

1. Même ordre, deux fiches qui ne diffèrent que par leurs thèmes : pistes différentes.
2. Deux ordres en tension aux causes différentes : familles de pistes différentes.
3. Même ordre, expérience « débutante » ou « avancée » : explications différentes, reliées à l'objectif ou à l'horizon.
4. Test 6 adapté : le cas 2 (Mateo, XOM) n'envoie pas l'explorateur.
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
}


def resume(r: dict) -> dict:
    return {"duree_s": r["duree_s"], "erreur": r["erreur"],
            "outils": [f"{e['agent']}:{e['outil']}" for e in r["trace"]],
            "finalite_supposee": r["intention"],
            "pistes": [{"famille": p["famille"], "piste": p["description"], "verdict": p["verdict"]["code"],
                        "score": p["score"], "raison": p["raison"]} for p in r["pistes"]],
            "explorateur": next(({"statut": a.get("statut"), "avis": a.get("avis")} for a in r["agents"]
                                 if a["nom"] == "explorateur"), None),
            "ancrage": r["ancrage"].get("statut"), "correction": r.get("correction"),
            "explication": r["explication"]}


def main() -> int:
    with ThreadPoolExecutor(max_workers=4) as pool:
        resultats = dict(zip(CAS, pool.map(lambda args: resume(inspection.inspecter(*args)), CAS.values())))
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
