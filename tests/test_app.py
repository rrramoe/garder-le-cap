"""Tests de l'interface avec AppTest : démarrage et les trois ordres de la démo, sans l'agent."""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
AVIS = "Explication de l'agent indisponible : le rapport ci-dessous vient directement du moteur de calcul"


@pytest.fixture
def sans_agent(monkeypatch):
    # Un None dans sys.modules fait échouer l'import : chemin de repli de l'interface.
    monkeypatch.setitem(sys.modules, "agent", None)
    monkeypatch.setitem(sys.modules, "agent.inspection", None)


def _demarrer() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def _textes(at: AppTest) -> str:
    morceaux = [m.value for m in at.markdown] + [c.value for c in at.caption]
    morceaux += [e.value for e in at.info] + [e.value for e in at.warning] + [e.value for e in at.error] + [e.value for e in at.success]
    return "\n".join(str(m) for m in morceaux)


def _verdict(at: AppTest) -> str:
    """Le texte de la carte du verdict, en tête du rapport."""
    cartes = [m.value for m in at.markdown if "1.9rem" in m.value]
    assert len(cartes) == 1
    return cartes[0]


def _inspecter(at: AppTest, persona: str) -> str:
    at.sidebar.radio(key="persona").set_value(persona).run()
    assert not at.exception, at.exception
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    return _textes(at)


def test_demarre_avec_bandeau(sans_agent):
    at = _demarrer()
    assert "Simulation à but éducatif. Aucune transaction réelle." in _textes(at)
    assert [t.label for t in at.tabs] == ["Fiche", "Portefeuille", "Ordre"]


def test_robert_tsla_en_tension(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    carte = _verdict(at)
    assert "En tension" in carte and "120 000 $" in carte and "15,0 %" in carte
    assert "pire baisse" in carte
    assert "92 000 $" in texte and "11,5 %" in texte  # taille compatible, en dollars et en %
    assert AVIS in texte
    assert "chercher_taille_compatible" in texte  # étapes : appels du moteur faits par l'interface


def test_mateo_xom_incompatible(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "mateo")
    carte = _verdict(at)
    assert "Incompatible" in carte and "20 000 $" in carte
    assert "Aucune taille n'est proposée" in texte
    assert AVIS in texte


def test_amira_nvda_hors_politique_aggrave(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "amira")
    carte = _verdict(at)
    assert "En tension" in carte and "3 500 $" in carte
    assert "Hors politique et aggrave" in texte
    assert AVIS in texte


def test_horizon_change_la_note_de_duree(sans_agent):
    at = _demarrer()
    _inspecter(at, "robert")
    at.selectbox(key="q_robert_horizon").set_value("15_plus").run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    texte = _textes(at)
    assert "Depuis l'inspection précédente" in texte
    assert "15 ans et plus" in texte
    assert "En tension" in _verdict(at)


def test_passer_ordre_simule(sans_agent):
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("robert").run()
    at.button(key="passer").click().run()
    assert not at.exception, at.exception
    assert "Aucune transaction réelle n'a eu lieu" in _textes(at)
    assert at.session_state["pf_robert"]["TSLA"] == pytest.approx(15.0)


def test_montant_en_dollars_et_type_d_ordre(sans_agent):
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("robert").run()
    at.number_input(key="o_robert_montant").set_value(92_000.0).run()
    assert "11,5 %" in _textes(at)  # part du portefeuille affichée à côté du montant
    at.selectbox(key="o_robert_type").set_value("limite").run()
    assert not at.exception, at.exception
    prix = [n for n in at.number_input if n.key.startswith("o_robert_prix_TSLA")]
    assert len(prix) == 1 and prix[0].value > 0  # pré-rempli avec le dernier prix connu en CAD
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    assert "Compatible" in _verdict(at)
    assert "exécuté à" in _textes(at)


def test_portefeuille_en_dollars_avec_anneaux(sans_agent):
    at = _demarrer()
    assert "800 000 $" in _textes(at)
    assert not at.exception, at.exception
