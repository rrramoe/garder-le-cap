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
    assert "En tension" in texte
    assert "ampleur de la pire baisse" in texte
    assert "11,5 %" in texte  # taille compatible
    assert AVIS in texte
    assert "chercher_taille_compatible" in texte  # étapes : appels du moteur faits par l'interface


def test_mateo_xom_incompatible(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "mateo")
    assert "Incompatible" in texte
    assert "Aucune taille n'est proposée" in texte
    assert AVIS in texte


def test_amira_nvda_hors_politique_aggrave(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "amira")
    assert "En tension" in texte
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
    assert "En tension" in texte


def test_passer_ordre_simule(sans_agent):
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("robert").run()
    at.button(key="passer").click().run()
    assert not at.exception, at.exception
    assert "Aucune transaction réelle n'a eu lieu" in _textes(at)
    assert at.session_state["pf_robert"]["TSLA"] == pytest.approx(15.0)
