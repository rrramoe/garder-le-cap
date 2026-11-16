"""Une vraie analyse par l'adresse publique, comme un navigateur : connexion au flux Streamlit (websocket), choix du
client par défaut, clic sur « Analyser l'ordre », lecture de ce que l'écran affiche jusqu'à la fin de l'analyse.

    python deploiement/essai_distant.py http://adresse/

Code de sortie 0 si le rapport s'affiche avec l'explication de l'agent, 1 sinon.
"""
from __future__ import annotations

import asyncio
import sys
import time

import websockets
from streamlit.proto import BackMsg_pb2, ForwardMsg_pb2

BOUTON = "inspecter"
AVIS_SANS_AGENT = "Explication de l'agent indisponible"
DELAI_S = 360


def textes(delta, sortie: list) -> None:
    el = delta.new_element if delta.HasField("new_element") else None
    if el is None:
        return
    for champ in ("markdown", "alert", "text", "heading"):
        if el.HasField(champ):
            sortie.append(getattr(el, champ).body)


def bouton(delta) -> str | None:
    if delta.HasField("new_element") and delta.new_element.HasField("button"):
        b = delta.new_element.button
        if BOUTON in b.id:
            return b.id
    return None


async def executer(ws, etats: list) -> tuple[list, str | None]:
    msg = BackMsg_pb2.BackMsg()
    msg.rerun_script.query_string = ""
    msg.rerun_script.page_script_hash = ""
    for e in etats:
        msg.rerun_script.widget_states.widgets.append(e)
    await ws.send(msg.SerializeToString())
    vus, bid = [], None
    fin = time.monotonic() + DELAI_S
    while time.monotonic() < fin:
        brut = await asyncio.wait_for(ws.recv(), timeout=DELAI_S)
        f = ForwardMsg_pb2.ForwardMsg()
        f.ParseFromString(brut)
        if f.HasField("delta"):
            textes(f.delta, vus)
            bid = bid or bouton(f.delta)
        if f.HasField("script_finished"):
            return vus, bid
    raise TimeoutError


async def principal(adresse: str) -> int:
    ws_url = adresse.rstrip("/").replace("http://", "ws://").replace("https://", "wss://") + "/_stcore/stream"
    async with websockets.connect(ws_url, subprotocols=["streamlit"], max_size=2 ** 26, open_timeout=20) as ws:
        vus, bid = await executer(ws, [])
        if not bid:
            print("Page chargée, mais bouton « Analyser l'ordre » introuvable.")
            return 1
        print("Page chargée par le flux public ; clic sur « Analyser l'ordre »…")
        clic = BackMsg_pb2.BackMsg().rerun_script.widget_states.widgets.add()
        clic.id, clic.trigger_value = bid, True
        debut = time.monotonic()
        vus, _ = await executer(ws, [clic])
    texte = "\n".join(vus)
    explication = next((t for t in vus if t.lstrip().startswith("**Verdict**")), "")
    agent = bool(explication) and AVIS_SANS_AGENT not in texte
    print(f"Analyse affichée en {time.monotonic() - debut:.0f} s ; explication de l'agent : "
          + (f"oui (« {explication.splitlines()[0][:140]} »)" if agent else "non"))
    return 0 if agent else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(principal(sys.argv[1])))
