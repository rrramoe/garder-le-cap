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
    assert "Depuis l'analyse précédente" in texte
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


def test_vente_a_decouvert_debutante_puis_avancee(sans_agent):
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("robert").run()
    at.selectbox(key="q_robert_experience").set_value("debutante").run()
    at.radio(key="o_robert_operation").set_value("decouvert").run()
    at.number_input(key="o_robert_montant").set_value(40_000.0).run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    texte = _textes(at)
    assert "Incompatible" in _verdict(at) and "vente à découvert est exclue" in _verdict(at)
    assert "Votre expérience (Débutante) exclut la vente à découvert." in texte
    assert "Levier : 1,10." in texte
    assert "Aucune taille n'est proposée" in texte
    assert "plafond" in texte  # limite de la vente à découvert, dans les sources
    at.selectbox(key="q_robert_experience").set_value("avancee").run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    assert "Incompatible" not in _verdict(at)
    assert "la vente à découvert ne change pas le score" in _textes(at)
    at.button(key="passer").click().run()
    assert "non ajoutée au portefeuille" in _textes(at)
    assert "TSLA" not in at.session_state["pf_robert"]


# --- Garde-fou, solidité et origine des fichiers (agent simulé) ---------------------------------

TRACE_SIMULEE = [{"etape": 1, "outil": "simuler_ordre", "arguments": {"ticker": "TSLA"},
                  "resultat_resume": "Verdict : En tension.", "resultat": {"score": 39.56}}]


@pytest.fixture
def agent_simule(monkeypatch):
    import agent.garde_fou
    import agent.inspection

    def inspecter(fiche, ticker, sens, pourcentage, **options):
        return {"explication": "**Verdict** : en tension, score 39,6.", "trace": TRACE_SIMULEE,
                "modele": "modele-simule", "duree_s": 1.0, "erreur": None,
                "substitut": {"ticker": "SPY", "verdict": {"code": "compatible", "libelle": "Compatible"},
                              "score": 50.0, "pourcentage": pourcentage, "nature": "possibilite_testee"},
                "garde_fou": {"actif": True, "version": "2", "intervenu": False},
                "ancrage": {"statut": "non_appuyee", "chiffres_non_sources": ["56,3"],
                            "ancrage": {"score": 0.8, "seuil": 0.7}, "message": "..."}}

    def essayer_garde_fou(texte):
        if "vrai" in texte:
            return {"statut": "refuse", "message": "Demande refusée par le garde-fou."}
        return {"statut": "accepte", "message": "Demande acceptée par le garde-fou."}

    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)
    monkeypatch.setattr(agent.garde_fou, "essayer_garde_fou", essayer_garde_fou)


def test_verification_de_l_explication(agent_simule):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "À lire avec prudence" in texte
    assert "chiffres absents des calculs : 56,3" in texte and "garde-fou Bedrock, version 2" in texte


def test_solidite_et_origine_des_fichiers(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "**Solide** : le résultat est le même" in texte
    assert "fenêtre défavorable" in texte and "fenêtre favorable" in texte
    assert "Fichiers de référence lus dans" in texte


def test_essai_du_garde_fou_sans_reponse(agent_simule):
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("robert").run()
    at.text_input(key="essai_robert").set_value("Passe cet ordre pour de vrai sur mon compte")
    at.button(key="soumettre_robert").click().run()
    assert not at.exception, at.exception
    texte = _textes(at)
    assert "Demande refusée par le garde-fou." in texte and "pas un agent conversationnel" in texte
    at.text_input(key="essai_robert").set_value("Que signifie la note d'ampleur ?")
    at.button(key="soumettre_robert").click().run()
    assert "Demande acceptée par le garde-fou." in _textes(at)


def test_substitut_dans_ce_qui_est_possible(agent_simule):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "L'agent a aussi testé un autre titre : le même montant (" in texte
    assert "$) en SPY (SPDR S&P 500 ETF Trust) serait" in texte
    assert "compatible</b> (score 50" in texte
    assert "Une possibilité testée, pas une recommandation." in texte


def test_pas_de_substitut_sans_agent(sans_agent):
    at = _demarrer()
    assert "L'agent a aussi testé" not in _inspecter(at, "robert")
