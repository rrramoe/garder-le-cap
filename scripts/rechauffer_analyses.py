"""Préchauffe la mémoire des analyses : l'ordre prérempli de chaque client enregistré, analysé une fois.

    python scripts/rechauffer_analyses.py

À lancer après chaque déploiement, sur la machine de l'application et avec la même configuration (`glc.env`) : les
analyses réussies sont écrites dans le fichier de mémoire (`.cache/analyses.json`, ou `GLC_MEMOIRE_FICHIER`), que
l'application relit ; un visiteur qui ouvre un client enregistré voit alors son analyse sans attendre, marquée
« analyse déjà faite pour cet ordre ». Une analyse en échec n'est pas gardée et le script le dit. Les analyses
tournent deux à la fois.
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import inspection, memoire  # noqa: E402
from moteur import references  # noqa: E402


def ordres_preremplis() -> list:
    clients = references.charger("personas")["personas"]
    return [(cid, c["ordre_demo"]) for cid, c in clients.items() if isinstance(c.get("ordre_demo"), dict)]


def rechauffer(cid: str, ordre: dict) -> str:
    debut = time.monotonic()
    r = inspection.inspecter(cid, ordre["ticker"], ordre["sens"], ordre["pourcentage"],
                             operation=ordre.get("operation", "comptant"))
    statut = (r.get("memoire") or {}).get("statut")
    garde = memoire.gardable(r)
    etat = "gardée" if garde else f"NON gardée ({r.get('erreur') or 'analyse incomplète ou en repli'})"
    return (f"{cid} : {ordre['sens']} de {ordre['pourcentage']} % de {ordre['ticker']} -> {statut}, {etat}, "
            f"{time.monotonic() - debut:.1f} s")


def main() -> int:
    ordres = ordres_preremplis()
    if not ordres:
        print("Aucun ordre prérempli dans les clients enregistrés.")
        return 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        lignes = list(pool.map(lambda o: rechauffer(*o), ordres))
    print("\n".join(lignes))
    print(f"Mémoire : {memoire.fichier()}")
    return 0 if all("NON gardée" not in l for l in lignes) else 1


if __name__ == "__main__":
    sys.exit(main())
