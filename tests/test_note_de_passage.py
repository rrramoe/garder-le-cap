"""Note de passage à 70 : aucun verdict, aucune direction, aucune taille compatible ne change.

Référence : tests/empreinte_echelle_50.json, enregistrée avec la note de passage à 50 juste avant le changement
(mêmes mesures, même géographie), sur les trois clients enregistrés et une grille d'ordres.
"""
import json
from pathlib import Path

import pytest

from moteur import api, donnees, notation

pytestmark = pytest.mark.skipif(not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
                                reason="data/prices_daily.csv absent")
_EMP = json.loads((Path(__file__).parent / "empreinte_echelle_50.json").read_text(encoding="utf-8"))
REF = _EMP["cas"]


def _client(nom):
    """Le client tel qu'il était à l'enregistrement de la référence (portefeuille compris)."""
    return {"persona": nom, "portefeuille_pct": _EMP["portefeuilles"][nom]}


def test_une_seule_note_de_passage_portee_par_chaque_resultat():
    assert notation.NOTE_DE_PASSAGE == api.NOTE_DE_PASSAGE == 70
    r = api.simuler_ordre("mateo", "SPY", "achat", 2)
    assert r["apres"]["note_de_passage"] == r["avant"]["note_de_passage"] == 70


def test_conversion_100_cible_70_limite_0_double_distance():
    assert notation.convertir(100) == 100 and notation.convertir(50) == 70 and notation.convertir(0) == 0
    assert notation.convertir(75) == pytest.approx(85)    # à mi-chemin dans la politique : 30 points pour la moitié
    assert notation.convertir(25) == pytest.approx(35)    # à mi-chemin au-delà : 70 points pour la moitié
    assert notation.note_lineaire(5, 0, 10) == 75         # note brute ; publiée : convertir(75) = 85


@pytest.mark.parametrize("cle", sorted(REF))
def test_verdicts_directions_et_tailles_inchanges(cle):
    attendu = REF[cle]
    parts = cle.split("|")
    if parts[1] == "etat":
        assert api.etat_des_lieux(_client(parts[0]))["dans_la_politique"] == attendu["dans_la_politique"]
        return
    client, ticker, sens, pct = _client(parts[0]), parts[1], parts[2], float(parts[3])
    r = api.simuler_ordre(client, ticker, sens, pct)
    # Deux cas de direction ajoutés depuis la référence : « revient » (ancien « rapproche » qui atteint la note de
    # passage) et « inchangé » (ancien « aggrave » sans changement de la note la plus faible).
    nouveaux = {"revient_dans_la_politique": "hors_politique_rapproche", "hors_politique_inchange": "hors_politique_aggrave"}
    cas = nouveaux.get(r["direction"]["cas"], r["direction"]["cas"])
    assert (r["verdict"]["code"], cas) == (attendu["verdict"], attendu["direction"])
    if "taille" in attendu:
        assert api.chercher_taille_compatible(client, ticker, sens, pct).get("taille_compatible_pct") == attendu["taille"]
