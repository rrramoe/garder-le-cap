"""Profils des instruments (partie B) : structure, source, absence = « indetermine », titres communs."""
import pytest

from moteur import api, instruments, profils, references


def _disponibles():
    try:
        references.charger("profils_instruments")
        return True
    except FileNotFoundError:
        return False


avec_profils = pytest.mark.skipif(not _disponibles(), reason="profils non construits (scripts/profils_instruments.py)")


@avec_profils
def test_profil_entreprise_et_fonds():
    p = api.lire_fiche_instrument("RY.TO")["profil"]
    assert p["type"] == "entreprise" and p["source"] == "yfinance_profils" and p["recupere_le"]
    for cle in ("industrie", "pays", "capitalisation", "chiffre_affaires", "benefice_net", "dette", "encaisse"):
        assert cle in p
    assert set(p["flux_tresorerie_signes"]) == {"exploitation", "investissement", "financement"}
    f = api.lire_fiche_instrument("SPY")
    assert f["profil"]["type"] == "fonds" and len(f["profil"]["dix_plus_grandes_positions"]) == 10
    assert "yfinance_profils" in {s["id"] for s in f["sources"]}
    assert api.lire_fiche_instrument("BTC-USD")["profil"]["type"] == "cryptoactif"


@avec_profils
def test_positions_deja_detenues_recalculees():
    port = {"MSFT": 6.0, "NVDA": 10.0, "XBB.TO": 84.0}
    top = profils.profil("SPY")["dix_plus_grandes_positions"]
    attendu = sum(h["poids"] for h in top if h["symbole"] in port)
    r = profils.positions_deja_detenues("SPY", port, set(instruments.toutes()))
    assert r["part_du_fonds"] == pytest.approx(attendu, abs=1e-6)
    assert {t["symbole"] for t in r["titres"]} == {h["symbole"] for h in top if h["symbole"] in port}


def test_symbole_canadien_ramene_a_l_univers():
    u = {"RY.TO", "AAPL"}
    assert profils.symbole_univers("RY", u, "XIU.TO") == "RY.TO"
    assert profils.symbole_univers("RY", u, "SPY") is None
    assert profils.symbole_univers("AAPL", u, "SPY") == "AAPL"


def test_profils_absents_donnent_indetermine(monkeypatch):
    def absent(nom):
        raise FileNotFoundError(nom)
    monkeypatch.setattr(profils.references, "charger", absent)
    assert profils.profil("RY.TO")["type"] == "indetermine"
    assert profils.positions_deja_detenues("SPY", {"AAPL": 5}, {"AAPL"}) == "indetermine"
