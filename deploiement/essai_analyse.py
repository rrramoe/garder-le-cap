"""Une vraie analyse, lancée sur la machine déployée : l'application elle-même (Streamlit AppTest), l'introduction
passée, le compte « robert » ouvert, clic sur « Analyser l'ordre » dans « Négocier ». Vérifie que le moteur rend un verdict, que l'équipe d'agents sur
Bedrock rend une explication et d'où viennent les fichiers de référence. Code de sortie 0 si tout répond.

    python deploiement/essai_analyse.py [client]
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

RACINE = Path(os.environ.get("GLC_RACINE") or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(RACINE))
os.chdir(RACINE)

from streamlit.testing.v1 import AppTest  # noqa: E402

from moteur import api  # noqa: E402


def main() -> int:
    client = sys.argv[1] if len(sys.argv) > 1 else "robert"
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=300)
    at.run()
    # Comme un visiteur : passer l'introduction, ouvrir le compte, aller au billet d'ordre.
    at.button(key="passer_intro").click().run()
    at.button(key=f"compte_{client}").click().run()
    at.radio(key="page").set_value("negocier").run()
    debut = time.monotonic()
    at.button(key="inspecter").click().run()
    duree = time.monotonic() - debut
    if at.exception:
        print(f"Exception dans l'application : {at.exception[0].value}")
        return 1
    rapport = at.session_state[f"rapport_{client}"]
    agent = rapport.get("agent") or {}
    verdict = (rapport.get("simulation") or {}).get("verdict")
    if isinstance(verdict, dict):
        verdict = verdict.get("libelle") or verdict.get("code")
    explication = agent.get("explication") or ""
    garde_fou = agent.get("garde_fou") or {}
    origine = api.origine_references()
    print(f"Client {client} : verdict « {verdict} » en {duree:.0f} s")
    print(f"Explication des agents : {len(explication.split())} mots" if explication else
          f"Explication des agents : absente ({agent.get('erreur') or 'raison inconnue'})")
    print("Garde-fou : " + (", ".join(f"{k}={v}" for k, v in garde_fou.items() if isinstance(v, (bool, str, int)))
                            or "non renseigné"))
    print(f"Références : {origine.get('message') or origine}")
    return 0 if verdict and explication else 1


if __name__ == "__main__":
    sys.exit(main())
