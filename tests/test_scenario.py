"""Scénario de plusieurs ordres et cause du verdict (moteur), sans nouvelle note."""
import pytest

from moteur import api, donnees

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)


def _jambe(ticker, sens, pct, **extra):
    return {"ticker": ticker, "sens": sens, "pourcentage": pct, **extra}


def test_scenario_d_un_seul_ordre_egal_a_simuler_ordre():
    a = api.simuler_scenario("robert", [_jambe("TSLA", "achat", 15)])
    b = api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert {k: v for k, v in a.items() if k != "ordres"} == b
    assert a["ordres"] == [{"ticker": "TSLA", "sens": "achat", "pourcentage": 15.0, "operation": "comptant"}]


def test_achat_partage_avec_un_fonds_diversifie():
    r = api.simuler_scenario("robert", [_jambe("TSLA", "achat", 7.5), _jambe("XIU.TO", "achat", 7.5)])
    assert "erreur" not in r
    avant = api.lire_fiche_client("robert")["portefeuille_pct"]
    assert r["portefeuille_apres_pct"]["TSLA"] == 7.5
    assert r["portefeuille_apres_pct"]["XIU.TO"] == avant["XIU.TO"] + 7.5
    assert "ZST.TO" not in r["portefeuille_apres_pct"]          # 15 % d'encaisse entièrement utilisés
    assert r["verdict"]["code"] in ("compatible", "en_tension", "incompatible")
    assert set(r) >= {"verdict", "score", "direction", "solidite", "cause", "ordres", "sources"}


def test_achat_paye_par_une_vente():
    r = api.simuler_scenario("robert", [_jambe("RY.TO", "achat", 10), _jambe("XBB.TO", "vente", 10)])
    avant = api.lire_fiche_client("robert")["portefeuille_pct"]
    apres = r["portefeuille_apres_pct"]
    assert apres["ZST.TO"] == avant["ZST.TO"]                      # l'encaisse ne bouge pas
    assert apres["XBB.TO"] == avant["XBB.TO"] - 10 and apres["RY.TO"] == avant["RY.TO"] + 10


def test_vente_qui_complete_l_encaisse():
    # 20 % d'achat : 15 % d'encaisse + 5 % de vente. Sans la vente, l'achat est refusé.
    assert "erreur" in api.simuler_ordre("robert", "XIU.TO", "achat", 20)
    r = api.simuler_scenario("robert", [_jambe("XIU.TO", "achat", 20), _jambe("XBB.TO", "vente", 5)])
    assert "erreur" not in r and "ZST.TO" not in r["portefeuille_apres_pct"]


def test_erreurs_du_scenario():
    assert "Encaisse insuffisante" in api.simuler_scenario(
        "robert", [_jambe("RY.TO", "achat", 15), _jambe("SPY", "achat", 5)])["erreur"]
    assert "ne peut pas dépasser" in api.simuler_scenario(
        "robert", [_jambe("RY.TO", "achat", 5), _jambe("XBB.TO", "vente", 20)])["erreur"]
    assert "1 à 4" in api.simuler_scenario("robert", [])["erreur"]
    assert "1 à 4" in api.simuler_scenario("robert", [_jambe(t, "achat", 1) for t in
                                                       ("SPY", "QQQ", "XIU.TO", "AGG", "GLD")])["erreur"]
    assert "deux fois" in api.simuler_scenario("robert", [_jambe("SPY", "achat", 1), _jambe("SPY", "achat", 2)])["erreur"]
    assert "erreur" in api.simuler_scenario("robert", [_jambe("XBB.TO", "vente", 50)])


def test_scenario_contrainte_stricte_de_n_importe_quel_ordre():
    r = api.simuler_scenario("mateo", [_jambe("ESGV", "achat", 4), _jambe("XOM", "achat", 4)])
    assert r["verdict"]["code"] == "incompatible" and "ecarte_esg" in r["contraintes_strictes"]["themes_violes"]
    assert r["cause"]["type"] == "contrainte_stricte"
    assert any(d["ticker"] == "XOM" and d["statut"] == "violee" for d in r["contraintes_strictes"]["detail"])


# --- Cause du verdict ----------------------------------------------------------------------------

def test_cause_risque():
    c = api.simuler_ordre("robert", "TSLA", "achat", 15)["cause"]
    assert c["type"] == "risque" and c["mesure"] == "ampleur" and c["sous_le_seuil"]
    assert c["valeur"] < c["limite"] < 0 and c["porte_par_l_ordre"] and c["part_du_risque_pct"]["TSLA"] > 0


def test_cause_plafond_d_une_action():
    c = api.simuler_ordre("robert", "RY.TO", "achat", 15)["cause"]
    assert c["type"] == "plafond" and c["mesure"] == "plus_grosse_action"
    assert c["instrument"] == "RY.TO" and c["poids"] == 21.0 and c["plafond"] == 15 and c["porte_par_l_ordre"]


def test_cause_plafond_d_un_fonds_et_crypto():
    c = api.simuler_ordre("robert", "XBB.TO", "achat", 15)["cause"]
    assert c["type"] == "plafond" and c["instrument"] == "XBB.TO" and c["poids"] == 50.0
    c = api.simuler_ordre("robert", "BTC-USD", "achat", 5)["cause"]
    assert c["type"] == "plafond" and c["mesure"] == "crypto" and c["porte_par_l_ordre"]


def test_cause_contrainte_stricte_et_ordre_compatible():
    assert api.simuler_ordre("mateo", "XOM", "achat", 8)["cause"]["type"] == "contrainte_stricte"
    c = api.simuler_ordre("robert", "XIU.TO", "achat", 2)["cause"]
    assert c["sous_le_seuil"] is False


def test_cause_sans_nouvelle_note():
    r = api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert r["cause"]["note"] == r["score"]
    for m in r["cause"]["autres_mesures_sous_le_seuil"]:
        assert r["apres"]["notes"][m["dimension"]]["mesures"][m["mesure"]]["note"] == m["note"] < 50


def test_cause_porte_le_detail_de_la_mesure():
    c = api.simuler_ordre("robert", "RY.TO", "achat", 15)["cause"]
    assert c["detail_mesure"]["poids"] == 21.0 and c["detail_mesure"]["plafond"] == 15
