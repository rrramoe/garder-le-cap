"""Tests d'acceptation 1 à 5 (section 12 de la spécification)."""
import json

import pytest

from moteur import api, donnees, instruments
from moteur.notation import baisses_etalons

TOL_POINTS = 0.3  # points de pourcentage, pour la pire baisse
TOL_ANNEES = 0.03  # années, pour le temps sous l'eau (arrondi des valeurs publiées au centième)

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)


def _note(r, dim):
    return r["notes"][dim]["note"]


# ---------------------------------------------------------------- test 1
def test_1_robert_tsla():
    r = api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert "erreur" not in r
    assert r["contraintes_strictes"]["violee"] is False
    assert r["verdict"]["code"] == "en_tension"
    # Modèle en cinq familles : la pire année (-17,7 % contre -10,58 % publiés) décide ; la pire baisse garde sa note.
    assert r["score"] == pytest.approx(16, abs=1)
    assert r["dimension_min"] == "risque"
    assert r["mesure_min"] == "pire_annee"
    assert r["apres"]["notes"]["risque"]["mesures"]["ampleur"]["note"] == pytest.approx(40, abs=1)
    # Avant l'ordre, Robert a 9 % d'actions hors du Canada pour une cible de 21 % (limite 11 %) : déjà hors politique.
    assert r["direction"]["cas"] == "hors_politique_aggrave"
    t = api.chercher_taille_compatible("robert", "TSLA", "achat", 15)
    assert t["lancee"] is True
    assert t["taille_compatible_pct"] == 7.0
    assert len(t["courbe"]) == 30


# ---------------------------------------------------------------- test 2
def test_2_mateo_xom():
    r = api.simuler_ordre("mateo", "XOM", "achat", 8)
    assert "erreur" not in r
    assert r["contraintes_strictes"]["violee"] is True
    assert r["contraintes_strictes"]["themes_violes"] == ["ecarte_esg"]
    assert r["verdict"]["code"] == "incompatible"
    for dim in ("objectif", "risque", "preferences"):
        assert _note(r["apres"], dim) >= 50
    t = api.chercher_taille_compatible("mateo", "XOM", "achat", 8)
    assert t["lancee"] is False
    assert t["taille_compatible_pct"] is None


# ---------------------------------------------------------------- test 3
def test_3_amira_nvda():
    r = api.simuler_ordre("amira", "NVDA", "achat", 7)
    assert "erreur" not in r
    assert r["contraintes_strictes"]["violee"] is False
    assert r["verdict"]["code"] == "en_tension"
    assert r["avant"]["score"] < 50
    assert r["direction"]["cas"] == "hors_politique_aggrave"
    e = api.etat_des_lieux("amira")
    assert e["statut"] == "hors_politique"


# ---------------------------------------------------------------- test 4
def test_4_sensibilite_horizon_robert():
    fiche = {"persona": "robert", "questionnaire": {"horizon": "15_plus"}}
    assert api.lire_fiche_client(fiche)["deduit"]["horizon_annees"]["valeur"] == 15
    r = api.simuler_ordre(fiche, "TSLA", "achat", 15)
    assert r["apres"]["notes"]["risque"]["mesures"]["duree"]["note"] > 90
    base = api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert base["apres"]["notes"]["risque"]["mesures"]["duree"]["note"] < 90


# ---------------------------------------------------------------- test 5 : valeurs de contrôle (7.3)
ETALONS = [
    ("conservateur", "reference", -13.2, 1.95),
    ("conservateur", "limite", -14.9, 1.97),
    ("equilibre", "reference", -12.7, 1.89),
    ("equilibre", "limite", -15.8, 1.93),
    ("croissance_maximale", "reference", -12.9, 1.53),
    ("croissance_maximale", "limite", -17.4, 1.55),
]


@pytest.mark.parametrize("profil,cas,baisse,tsl", ETALONS)
def test_5_etalons(profil, cas, baisse, tsl):
    e = baisses_etalons(profil)[cas]
    assert e["pire_baisse"] * 100 == pytest.approx(baisse, abs=TOL_POINTS)
    assert e["temps_sous_l_eau_annees"] == pytest.approx(tsl, abs=TOL_ANNEES)


PERSONAS = [
    ("robert", None, -8.8, 1.95),
    ("robert", ("TSLA", 15), -18.0, 2.49),
    ("mateo", None, -13.4, 1.55),
    ("mateo", ("XOM", 8), -10.1, 0.93),
    ("amira", None, -29.7, 1.60),
    ("amira", ("NVDA", 7), -34.2, 1.51),
]


@pytest.mark.parametrize("client,ordre,baisse,tsl", PERSONAS)
def test_5_personas(client, ordre, baisse, tsl):
    if ordre is None:
        risque = api.etat_des_lieux(client)["notes"]["risque"]
    else:
        risque = api.simuler_ordre(client, ordre[0], "achat", ordre[1])["apres"]["notes"]["risque"]
    assert risque["mesures"]["ampleur"]["pire_baisse"] * 100 == pytest.approx(baisse, abs=TOL_POINTS)
    assert risque["mesures"]["duree"]["temps_sous_l_eau_annees"] == pytest.approx(tsl, abs=TOL_ANNEES)


@pytest.mark.parametrize("client,ticker,pct,avant,apres", [
    ("robert", "TSLA", 15, 68, 40),
    ("mateo", "XOM", 8, 89, 94),
    ("amira", "NVDA", 7, 15, 2),
])
def test_5_notes_de_risque(client, ticker, pct, avant, apres):
    # Les notes attendues sont des entiers calculés à partir des valeurs de contrôle
    # arrondies (ex. Robert avant : 100 - 50 x 1,95 / 3 = 67,5 -> 68 ; le moteur mesure
    # T = 1,952 an, d'où 67,47). Tolérance : 1 point.
    r = api.simuler_ordre(client, ticker, "achat", pct)
    # Pire baisse et durée sous le sommet : mesures d'avant le modèle en cinq familles, valeurs inchangées.
    def anciennes(bloc):
        m = r[bloc]["notes"]["risque"]["mesures"]
        return min(m["ampleur"]["note"], m["duree"]["note"])
    assert anciennes("avant") == pytest.approx(avant, abs=1)
    assert anciennes("apres") == pytest.approx(apres, abs=1)


def test_volatilite_spy_et_speculatifs():
    assert instruments.meta()["volatilite_spy_cad"] == pytest.approx(0.165, abs=0.003)
    spec = {t for t, f in instruments.toutes().items() if f["etiquettes"]["speculatif"]["valeur"] is True}
    assert spec == {"AMZN", "NVDA", "TSLA", "SHOP.TO", "BTC-USD", "ETH-USD"}
