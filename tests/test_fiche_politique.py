"""Fiche enrichie : capacité à supporter une perte, besoin de liquidité, type de compte.

Chaque ajout est neutre avec sa réponse par défaut ; chaque réponse non neutre crée une règle.
"""
import pytest

from moteur import api, client, donnees, references

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)

PROFILS = references.charger("profils")["profils"]


@pytest.mark.parametrize("persona", ["amira", "mateo", "robert"])
def test_personas_reponses_neutres(persona):
    q = references.charger("personas")["personas"][persona]["questionnaire"]
    assert q["capacite_perte"] == q["fluctuations"]
    d = api.lire_fiche_client(persona)["deduit"]
    assert d["profil"]["decide_par"] == "les_deux"


def test_capacite_par_defaut_suit_les_fluctuations():
    r = api.lire_fiche_client({"persona": "robert", "questionnaire": {"fluctuations": "elevees"}})
    assert r["questionnaire"]["capacite_perte"] == "elevees"
    assert r["deduit"]["profil"]["valeur"] == "croissance_maximale"


def test_capacite_plus_basse_change_le_profil_les_fourchettes_et_les_etalons():
    tolerance = api.lire_fiche_client({"persona": "amira"})
    capacite = api.lire_fiche_client({"persona": "amira", "questionnaire": {"capacite_perte": "faibles_moderees"}})
    p = capacite["deduit"]["profil"]
    assert (p["accepte"]["valeur"], p["permis"]["valeur"], p["valeur"], p["decide_par"]) == \
        ("croissance_maximale", "conservateur", "conservateur", "capacite")
    assert capacite["deduit"]["fourchettes_pct"]["valeur"] == PROFILS["conservateur"]["fourchettes"]
    assert tolerance["deduit"]["fourchettes_pct"]["valeur"] == PROFILS["croissance_maximale"]["fourchettes"]
    assert capacite["deduit"]["crypto_pct"]["valeur"] != tolerance["deduit"]["crypto_pct"]["valeur"]
    assert capacite["deduit"]["coherence_objectif"]["valeur"] == "a_verifier"
    e_tol = api.etat_des_lieux({"persona": "amira"})["notes"]["risque"]["etalons"]
    e_cap = api.etat_des_lieux({"persona": "amira", "questionnaire": {"capacite_perte": "faibles_moderees"}})
    assert e_cap["notes"]["risque"]["etalons"] != e_tol


def test_capacite_plus_haute_ne_change_rien():
    r = api.lire_fiche_client({"persona": "robert", "questionnaire": {"capacite_perte": "elevees"}})
    assert r["deduit"]["profil"]["valeur"] == "conservateur"
    assert r["deduit"]["profil"]["decide_par"] == "fluctuations"
    assert r["deduit"]["fourchettes_pct"] == api.lire_fiche_client("robert")["deduit"]["fourchettes_pct"]


def test_capacite_invalide():
    r = api.lire_fiche_client({"persona": "robert", "questionnaire": {"capacite_perte": "illimitee"}})
    assert set(r) == {"erreur"} and "capacite_perte" in r["erreur"]


def test_sources_de_la_capacite():
    ids = {s["id"] for s in api.lire_fiche_client("robert")["sources"]}
    assert {"acvm_capacite_perte", "hypothese_capacite_libelles"} <= ids
    assert client.CHAMPS.index("capacite_perte") == client.CHAMPS.index("fluctuations") + 1


# ---------------------------------------------------------------- besoin de liquidités

BESOIN_10 = {"persona": "mateo", "questionnaire": {"besoin_liquidite": "jusqu_10"}}


def test_besoin_aucun_ne_change_rien():
    r = api.lire_fiche_client({"persona": "mateo", "questionnaire": {"besoin_liquidite": "aucun"}})
    assert r["deduit"]["fourchettes_pct"]["valeur"] == PROFILS["equilibre"]["fourchettes"]
    assert r["deduit"]["besoin_liquidite_pct"]["valeur"] == 0
    assert "hypothese_besoin_liquidite" not in {s["id"] for s in r["sources"]}


@pytest.mark.parametrize("choix,besoin", [("jusqu_10", 10), ("10_25", 25), ("25_40", 40)])
def test_besoin_decale_la_seule_classe_liquidites(choix, besoin):
    r = api.lire_fiche_client({"persona": "amira", "questionnaire": {"besoin_liquidite": choix}})
    f, f0 = r["deduit"]["fourchettes_pct"]["valeur"], PROFILS["croissance_maximale"]["fourchettes"]
    liq, liq0 = f["liquidites"], f0["liquidites"]
    assert (liq["min"], liq["cible"], liq["max"]) == (liq0["min"] + besoin, liq0["cible"] + besoin,
                                                      min(100, liq0["max"] + besoin))
    assert {c: v for c, v in f.items() if c != "liquidites"} == {c: v for c, v in f0.items() if c != "liquidites"}
    assert r["deduit"]["besoin_liquidite_pct"]["phrase"] == \
        f"Vous gardez au moins {besoin} % en liquidités pour vos besoins de l'année."
    assert "hypothese_besoin_liquidite" in {s["id"] for s in r["sources"]}


def test_besoin_achat_paye_par_l_encaisse_passe_en_tension():
    sans = api.simuler_ordre("mateo", "AGG", "achat", 2)
    avec = api.simuler_ordre(BESOIN_10, "AGG", "achat", 2)
    assert sans["verdict"]["code"] == "compatible"
    assert avec["verdict"]["code"] == "en_tension"
    assert avec["mesure_min"] == "classe_liquidites"
    m = avec["apres"]["notes"]["diversification"]["mesures"]["classe_liquidites"]
    assert (m["poids"], m["min"], m["cible"]) == (8, 10, 15)
    assert m["note"] == pytest.approx(30.0)  # formule de classe inchangée : 100 - 50 x (15 - 8) / (15 - 10)
