"""Tests de l'interface avec AppTest : démarrage et les trois ordres de la démo, sans l'agent."""

import sys
import time
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
# ---------------------------------------------------------------- analyse en direct

def _module_agent_factice(avec_crochet: bool):
    """Faux agent qui suit le contrat de agent/inspection.py et annonce ses étapes."""
    import types

    def inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant", sur_etape=None):
        trace = []
        appels = [("lire_fiche_client", "Je lis votre fiche.", "Profil lu."),
                  ("simuler_ordre", "Je simule l'ordre.", "Verdict simulé."),
                  ("chercher_taille_compatible", "Je cherche le montant compatible.", "Taille trouvée.")]
        for n, (outil, libelle, resume) in enumerate(appels, start=1):
            if sur_etape and n > 1:
                sur_etape({"moment": "redaction", "agent": "principal"})  # tour du modèle entre deux outils
            if sur_etape:
                sur_etape({"moment": "debut_outil", "etape": n, "outil": outil, "arguments": {"ticker": ticker},
                           "libelle": libelle, "agent": "principal"})
                time.sleep(0.05)
                sur_etape({"moment": "fin_outil", "etape": n, "outil": outil, "resultat_resume": resume})
            trace.append({"etape": n, "outil": outil, "arguments": {"ticker": ticker},
                          "resultat_resume": resume, "resultat": {}})
        for moment in ("redaction", "verification", "fin"):
            if sur_etape:
                sur_etape({"moment": moment})
        return {"explication": "Texte factice de l'agent.", "trace": trace, "modele": "factice",
                "duree_s": 0.2, "erreur": None}

    if not avec_crochet:
        def inspecter(client, ticker, sens, pourcentage, modele=None, operation="comptant", _f=inspecter):  # noqa: F811
            return _f(client, ticker, sens, pourcentage, modele, operation)

    module = types.ModuleType("agent.inspection")
    module.inspecter = inspecter
    return module


@pytest.fixture
def agent_en_direct(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "agent", types.ModuleType("agent"))
    monkeypatch.setitem(sys.modules, "agent.inspection", _module_agent_factice(True))


@pytest.fixture
def agent_sans_crochet(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "agent", types.ModuleType("agent"))
    monkeypatch.setitem(sys.modules, "agent.inspection", _module_agent_factice(False))


def test_analyse_en_direct_replie_en_etapes(agent_en_direct):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "En tension" in _verdict(at)  # le rapport du moteur reste en tête
    assert "Texte factice de l'agent." in texte
    etiquettes = [e.label for e in at.status]
    assert any(l.startswith("Étapes de l'analyse · 3 étape(s)") for l in etiquettes), etiquettes
    assert at.status[0].state == "complete"
    assert "Taille trouvée." in texte  # résumé de l'étape, dans la liste repliée
    assert "Agent principal ·" in texte  # l'agent au travail reste nommé dans « Étapes de l'analyse »
    assert at.status[0].label.startswith("Étapes de l'analyse · 3 étape(s)")


def test_agent_sans_crochet_garde_l_attente_simple(agent_sans_crochet):
    at = _demarrer()
    texte = _inspecter(at, "mateo")
    assert "Incompatible" in _verdict(at)
    assert "Texte factice de l'agent." in texte
    assert "Étapes de l'analyse" in [e.label for e in at.expander]


def test_rendu_en_direct_marque_les_etapes():
    sys.path.insert(0, str(Path(APP).parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("app_pour_rendu", APP)
    # Lire la fonction sans lancer la page : on l'extrait du source.
    import ast
    source = Path(APP).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    noeuds = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in ("rendu_en_direct", "nom_agent")
              or isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("LIBELLES_PHASES", "NOMS_AGENTS")
                                                   for t in n.targets)]
    espace: dict = {}
    exec(compile(ast.Module(body=noeuds, type_ignores=[]), APP, "exec"), espace)
    rendu = espace["rendu_en_direct"](
        [{"libelle": "Je lis votre fiche.", "fini": True, "resume": "Profil lu.", "agent": "principal"},
         {"libelle": "Je rédige l'explication.", "phase": True, "fini": True},
         {"libelle": "Je simule l'ordre.", "fini": False, "resume": "", "agent": "explorateur"}])
    lignes = rendu.splitlines()
    assert lignes[0].rstrip() == "- ✓ Je lis votre fiche. :gray[· Agent principal]" and "Profil lu." in rendu
    assert lignes[-1] == "- … **Je simule l'ordre.** :gray[· Agent explorateur]"  # ordre d'arrivée gardé
    assert "- ✓ Je rédige l'explication." in lignes


# --- Pistes testées par l'explorateur et correction du texte ---------------------------------------

@pytest.fixture
def equipe_simulee(monkeypatch):
    import agent.inspection

    def inspecter(fiche, ticker, sens, pourcentage, **options):
        return {"explication": "**Verdict** : en tension.", "trace": TRACE_SIMULEE, "modele": "modele-simule",
                "duree_s": 1.0, "erreur": None, "substitut": None,
                "intention": "l'achat semble viser une action de croissance.",
                "pistes": [{"famille": "combinaison", "libelle_famille": "Combinaison",
                            "description": "Montant plus petit avec un complément",
                            "ordres": [{"ticker": "TSLA", "sens": "achat", "pourcentage": 6.0},
                                       {"ticker": "SPY", "sens": "achat", "pourcentage": 4.0}],
                            "raison": "Garde une part de croissance avec moins de risque.",
                            "verdict": {"code": "compatible", "libelle": "Compatible"}, "score": 50.0,
                            "direction": {"cas": "reste_dans_la_politique"}, "etape": 6}],
                "agents": [{"nom": "principal"}, {"nom": "explorateur", "statut": "termine"}],
                "correction": {"faite": True, "motifs": ["Le chiffre 97,3 ne figure dans aucun résultat d'outil."],
                               "reussie": True},
                "garde_fou": {"actif": True, "version": "2", "intervenu": False},
                "ancrage": {"statut": "appuyee", "chiffres_non_sources": [], "message": "..."}}

    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)


def test_pistes_testees_et_correction(equipe_simulee):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "Pistes testées" in texte
    assert "Finalité supposée de l'achat (hypothèse de l'agent) :* l'achat semble viser" in texte
    assert "**Combinaison** : achat de 6,0 % de TSLA (" in texte and "achat de 4,0 % de SPY (" in texte
    assert "compatible</b> (score 50" in texte and "Garde une part de croissance" in texte
    assert "pas des recommandations" in texte and "L'agent a aussi testé" not in texte
    assert "L'agent a corrigé son texte après vérification." in texte


# ---------------------------------------------------------------- nouveau client

def test_nouveau_client_tout_le_parcours(sans_agent):
    from moteur import api
    at = _demarrer()
    at.sidebar.radio(key="persona").set_value("nouveau").run()
    assert not at.exception, at.exception
    texte = _textes(at)
    assert "réponses par défaut" in texte  # aucune réponse héritée d'un exemple
    assert at.session_state["pf_nouveau"] == {"ZST.TO": 100.0}

    # Fiche : choisie à l'écran.
    for champ, valeur in (("horizon", "15_plus"), ("fluctuations", "elevees"), ("capacite_perte", "elevees"),
                          ("experience", "avancee"), ("objectif", "croissance_long_terme")):
        at.selectbox(key=f"q_nouveau_{champ}").set_value(valeur).run()
    at.radio(key="q_nouveau_theme_ecarte_esg").set_value("exclure").run()
    assert not at.exception, at.exception

    # Portefeuille : valeur totale, puis positions ; le reste en liquidités ; refus au-delà de la valeur.
    at.number_input(key="nc_nouveau_valeur").set_value(200_000.0).run()
    for titre, montant in (("XIU.TO", 80_000.0), ("SPY", 60_000.0)):
        at.selectbox(key="nc_nouveau_titre").set_value(titre).run()
        at.number_input(key="nc_nouveau_montant").set_value(montant).run()
        at.button(key="nc_nouveau_ajouter").click().run()
        assert not at.exception, at.exception
    pf = at.session_state["pf_nouveau"]
    assert pf["XIU.TO"] == pytest.approx(40.0) and pf["SPY"] == pytest.approx(30.0)
    assert pf["ZST.TO"] == pytest.approx(30.0)
    at.selectbox(key="nc_nouveau_titre").set_value("QQQ").run()
    at.number_input(key="nc_nouveau_montant").set_value(70_000.0).run()
    at.button(key="nc_nouveau_ajouter").click().run()
    assert "Refusé : le total dépasserait la valeur du portefeuille" in _textes(at)
    assert "QQQ" not in at.session_state["pf_nouveau"]
    assert "200 000 $" in _textes(at)

    # Ordre sur un titre hors des ordres de démonstration, analysé par le même chemin que les exemples.
    at.selectbox(key="o_nouveau_ticker").set_value("AAPL").run()
    at.number_input(key="o_nouveau_montant").set_value(20_000.0).run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    carte = _verdict(at)
    assert "20 000 $" in carte and "AAPL" in carte and "10,0 %" in carte
    fiche = {"id": "nouveau", "nom": "Nouveau client",
             "questionnaire": {"objectif": "croissance_long_terme", "horizon": "15_plus", "fluctuations": "elevees",
                               "capacite_perte": "elevees", "besoin_liquidite": "aucun", "experience": "avancee",
                               "themes": {"ecarte_esg": "exclure", "speculatif": "neutre", "crypto": "neutre",
                                          "techno": "neutre", "etablie": "neutre"}},
             "portefeuille_pct": {"ZST.TO": 30.0, "XIU.TO": 40.0, "SPY": 30.0}}
    attendu = api.simuler_ordre(fiche, "AAPL", "achat", 10.0)
    assert "erreur" not in attendu
    assert attendu["verdict"]["libelle"] in carte
    assert AVIS in _textes(at)

    # Ordre simulé : appliqué au portefeuille de la session du nouveau client.
    at.button(key="passer").click().run()
    assert at.session_state["pf_nouveau"]["AAPL"] == pytest.approx(10.0)


def test_fiche_d_un_nouveau_client_acceptee_par_le_moteur():
    from moteur import api
    fiche = {"id": "nouveau", "nom": "Nouveau client",
             "questionnaire": {"objectif": "croissance_equilibree", "horizon": "5_8", "fluctuations": "moderees",
                               "capacite_perte": "moderees", "besoin_liquidite": "aucun", "experience": "debutante",
                               "themes": {}},
             "portefeuille_pct": {"ZST.TO": 100.0}}
    f = api.lire_fiche_client(fiche)
    assert "erreur" not in f and f["id"] == "nouveau"
    assert "erreur" not in api.etat_des_lieux(fiche)
    assert "erreur" not in api.simuler_ordre(fiche, "MSFT", "achat", 5)
