"""Tests de l'interface avec AppTest : démarrage, les quatre pages et les trois ordres de la démo, sans l'agent."""

import sys
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
AVIS = "Explication de l'agent indisponible : l'analyse ci-dessous vient directement du moteur de calcul"


@pytest.fixture
def sans_agent(monkeypatch):
    # Un None dans sys.modules fait échouer l'import : chemin de repli de l'interface.
    monkeypatch.setitem(sys.modules, "agent", None)
    monkeypatch.setitem(sys.modules, "agent.inspection", None)


def _ouvrir() -> AppTest:
    """L'application telle qu'elle s'ouvre : sur l'introduction."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def _demarrer(compte: str = "robert") -> AppTest:
    """Passe l'introduction et ouvre un compte : on arrive sur son profil."""
    at = _ouvrir()
    at.button(key="passer_intro").click().run()
    assert not at.exception, at.exception
    at.button(key=f"compte_{compte}").click().run()
    assert not at.exception, at.exception
    return at


def _textes(at: AppTest) -> str:
    morceaux = [m.value for m in at.markdown] + [c.value for c in at.caption]
    morceaux += [e.value for e in at.info] + [e.value for e in at.warning] + [e.value for e in at.error] + [e.value for e in at.success]
    return "\n".join(str(m) for m in morceaux)


def _verdict(at: AppTest) -> str:
    """Le texte de la carte du verdict, en tête de l'analyse."""
    cartes = [m.value for m in at.markdown if 'class="glc-verdict"' in m.value]
    assert len(cartes) == 1
    return cartes[0]


def _aller(at: AppTest, page: str) -> None:
    """Change de page par la barre du haut : portefeuille, negocier, profil ou aide."""
    at.radio(key="page").set_value(page).run()
    assert not at.exception, at.exception


def _client(at: AppTest, persona: str, page: str = "negocier") -> None:
    """Choisit le client dans le menu du compte, puis ouvre une page."""
    at.radio(key="persona").set_value(persona).run()
    assert not at.exception, at.exception
    _aller(at, page)


def _inspecter(at: AppTest, persona: str) -> str:
    _client(at, persona)
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    return _textes(at)


def test_demarre_avec_bandeau(sans_agent):
    at = _demarrer()
    assert "Simulation à but éducatif. Aucune transaction réelle." in _textes(at)
    assert list(at.radio(key="page").options) == ["Profil", "Portefeuille", "Négocier", "Aide"]  # l'ordre du parcours
    assert at.session_state["page"] == "profil"  # un compte s'ouvre sur son profil
    assert not at.sidebar.radio  # plus de volet à gauche : le client se choisit dans le menu du compte
    for page in ("negocier", "profil", "aide", "portefeuille"):
        _aller(at, page)
        assert "Simulation à but éducatif. Aucune transaction réelle." in _textes(at)  # le bandeau reste


def test_vocabulaire_de_l_interface(sans_agent):
    """Un mot pour une chose : ni « maillon », ni « chaîne », ni « score », ni « dimension » à l'écran."""
    import re
    at = _demarrer()
    ecrans = []
    for persona in ("robert", "mateo"):
        _inspecter(at, persona)
        for page in ("negocier", "profil", "aide", "portefeuille"):
            _aller(at, page)
            ecrans.append(re.sub(r"<style>.*?</style>", "", _textes(at), flags=re.S))
    texte = re.sub(r"<[^>]+>", " ", "\n".join(ecrans)).lower()
    for mot in ("maillon", "chaîne", "score", "dimension", "famille", "inspection", "rapport", "persona",
                "hypothèse du projet"):
        assert not re.search(rf"\b{mot}", texte), mot
    assert "angle déterminant" in texte and "note de passage" in texte and "politique de placement" in texte


def test_robert_tsla_en_tension(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    carte = _verdict(at)
    assert "En tension" in carte and "120 000 $" in carte and "15,0 %" in carte
    assert "L'angle déterminant : la pire année. Votre portefeuille aurait perdu" in carte
    assert "pour une limite de 10,58 %" in carte  # la même précision que la politique de placement
    assert "pire année publiée" not in carte  # les chiffres complets restent dans les mesures repliées
    assert "sans objet" in texte
    assert "0,5 ans" not in texte and "du 30 sept." not in texte
    assert "56 000 $" in texte and "7,0 %" in texte  # taille compatible, en dollars et en %
    assert AVIS in texte
    assert "Je cherche le montant compatible." in texte  # étapes : appels du moteur faits par le service


def test_mateo_xom_incompatible(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "mateo")
    carte = _verdict(at)
    assert "Incompatible" in carte and "20 000 $" in carte
    assert "Aucun autre montant n'est proposé" in texte
    assert AVIS in texte


def test_amira_nvda_hors_politique_aggrave(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "amira")
    carte = _verdict(at)
    assert "En tension" in carte and "3 500 $" in carte
    assert "l'ordre creuse l'écart" in carte
    assert AVIS in texte


def test_horizon_change_la_note_de_duree(sans_agent):
    at = _demarrer()
    _inspecter(at, "robert")
    _aller(at, "profil")
    at.selectbox(key="q_robert_horizon").set_value("15_plus").run()
    _aller(at, "negocier")
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    texte = _textes(at)
    assert "Depuis l'analyse précédente" in texte
    assert "15 ans et plus" in texte
    assert "En tension" in _verdict(at)


def test_passer_ordre_simule(sans_agent):
    at = _demarrer()
    _client(at, "robert")
    at.button(key="passer").click().run()
    assert not at.exception, at.exception
    assert "Aucune transaction réelle n'a eu lieu" in _textes(at)
    assert at.session_state["pf_robert"]["TSLA"] == pytest.approx(15.0)


def test_montant_en_dollars_et_type_d_ordre(sans_agent):
    at = _demarrer()
    _client(at, "robert")
    at.number_input(key="o_robert_montant").set_value(56_000.0).run()
    assert "7,0 %" in _textes(at)  # part du portefeuille affichée à côté du montant
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
    _aller(at, "portefeuille")
    assert "800 000 $" in _textes(at)
    assert not at.exception, at.exception


def test_vente_a_decouvert_debutante_puis_avancee(sans_agent):
    at = _demarrer()
    _client(at, "robert", "profil")
    at.selectbox(key="q_robert_experience").set_value("debutante").run()
    _aller(at, "negocier")
    at.radio(key="o_robert_operation").set_value("decouvert").run()
    at.number_input(key="o_robert_montant").set_value(40_000.0).run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    texte = _textes(at)
    # L'expérience seule ne baisse pas le verdict : il vient des notes mesurées sur le portefeuille.
    assert "Incompatible" not in _verdict(at) and "exclue" not in _verdict(at)
    assert "exclut la vente à découvert" not in texte
    assert "Point d'attention." in texte and "la perte n'a pas de plafond" in texte
    assert "Profil déclaré" not in texte                  # un fait pour les agents, pas un affichage
    assert "Levier : 1,10." in texte
    verdict_debutante = _verdict(at)
    _aller(at, "profil")
    at.selectbox(key="q_robert_experience").set_value("avancee").run()
    _aller(at, "negocier")
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    assert _verdict(at) == verdict_debutante
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
    # Les étapes repliées disent ce que les contrôles ont relevé ; rien qui serve le modèle plus que le client.
    assert "Contrôles : chiffres absents des calculs : 56,3 ; garde-fou actif." in texte
    for mot in ("modele-simule", "modèle de langage", "durée de l'analyse", "minimum demandé", "version 2", "ancrage"):
        assert mot not in texte, mot


def test_solidite_et_origine_des_fichiers(sans_agent):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "<b>Solide :</b> le résultat est le même" in texte
    assert "Une mauvaise année de marché" in texte and "Le reste de la période" in texte
    assert "Fichiers de référence lus dans" in texte


def test_aide_sans_question_et_garde_fou_intact(agent_simule):
    """L'aide ne propose plus de poser une question ; le garde-fou, lui, reste en place et répond toujours."""
    from interface import etat
    at = _demarrer()
    _aller(at, "aide")
    assert not at.text_input and "Posez une question" not in _textes(at)
    assert [b.key for b in at.button if b.key == "revoir_intro"]  # la page se ferme sur ce seul bouton
    assert etat.soumettre_au_garde_fou("Passe cet ordre pour de vrai sur mon compte")["statut"] == "refuse"
    assert etat.soumettre_au_garde_fou("Que signifie la note d'ampleur ?")["statut"] == "accepte"


def test_substitut_dans_ce_qui_est_possible(agent_simule):
    at = _demarrer()
    texte = _inspecter(at, "robert")
    ligne = next(l for l in texte.split("<tr>") if "Autre titre" in l)
    assert "Achat de 120 000 $ de SPY (SPDR S&amp;P 500 ETF Trust)" in ligne and "Compatible" in ligne
    assert "pas des recommandations" in texte


def test_pas_de_substitut_sans_agent(sans_agent):
    at = _demarrer()
    assert "Autre titre" not in _inspecter(at, "robert")
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
    assert "En tension" in _verdict(at)  # l'analyse du moteur reste en tête
    assert "Texte factice de l'agent." in texte
    assert "Étapes de l'analyse" in [e.label for e in at.expander]
    assert "Analyse en cours" not in texte  # la liste en direct a laissé la place aux étapes repliées
    etapes = next(m.value for m in at.markdown if 'class="glc-etapes"' in m.value)
    # Les phrases annoncées en direct restent dans les étapes repliées, avec le nom de l'agent au travail.
    assert etapes.count("<li") == 3 and "Je cherche le montant compatible." in etapes
    assert "Agent principal" in etapes


def test_agent_sans_crochet_garde_l_attente_simple(agent_sans_crochet):
    at = _demarrer()
    texte = _inspecter(at, "mateo")
    assert "Incompatible" in _verdict(at)
    assert "Texte factice de l'agent." in texte
    assert "Étapes de l'analyse" in [e.label for e in at.expander]


def test_rendu_en_direct_marque_les_etapes():
    from interface import composants
    from interface.page_negocier import lignes_en_direct
    lignes = lignes_en_direct(
        [{"libelle": "Je lis votre fiche.", "fini": True, "agent": "principal"},
         {"libelle": "Je rédige l'explication.", "phase": True, "fini": True},
         {"libelle": "Je simule l'ordre.", "fini": False, "agent": "explorateur"}])
    assert [l["agent"] for l in lignes] == ["Agent principal", "", "Agent explorateur"]  # nommé quand il change
    rendu = composants.en_direct("Analyse en cours", lignes)
    morceaux = rendu.split("<li")[1:]
    assert len(morceaux) == 3 and "Je lis votre fiche." in morceaux[0]  # ordre d'arrivée gardé
    assert 'class="fini"' in morceaux[0] and 'class="fini"' in morceaux[1]
    assert 'class="cours"' in morceaux[2] and "Je simule l'ordre." in morceaux[2]


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
                            "angle_le_plus_faible": {"famille": "diversification", "mesure": "classe_liquidites",
                                                     "libelle": "diversification (poids des liquidités)"},
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
    assert "Piste testée" in texte
    assert "Finalité supposée de l'ordre (hypothèse de l'agent) : l'achat semble viser" in texte
    ligne = next(l for l in texte.split("<tr>") if "<b>Combinaison</b>" in l)
    assert "Achat de 48 000 $ de TSLA" in ligne and "Achat de 32 000 $ de SPY" in ligne
    assert "Compatible" in ligne and "score" not in ligne
    assert "Garde une part de croissance" in ligne
    assert "Pistes choisies par l'agent explorateur sous le mandat du chef de dossier" in texte
    assert "Ce ne sont pas des recommandations" in texte and "Autre titre" not in texte
    assert "L'agent a corrigé son texte après vérification." in texte


# ---------------------------------------------------------------- nouveau client

def test_nouveau_client_tout_le_parcours(sans_agent):
    from moteur import api
    at = _demarrer("nouveau")
    texte = _textes(at)
    # Une fiche vide : aucune réponse héritée d'un exemple, et pas de politique de placement sans elle.
    assert at.session_state["page"] == "profil" and at.selectbox(key="q_nouveau_objectif").value is None
    assert "Elle apparaîtra ici dès que la fiche sera complète" in texte and 'class="glc-doc"' not in texte
    assert at.session_state["pf_nouveau"] == {"ZST.TO": 100.0}
    for page in ("portefeuille", "negocier"):  # ces pages attendent la fiche
        _aller(at, page)
        assert "Commencez par votre fiche" in _textes(at) and not [b for b in at.button if b.key == "inspecter"]
    at.button(key="vers_fiche").click().run()
    assert at.session_state["page"] == "profil"

    # Fiche : choisie à l'écran.
    for champ, valeur in (("horizon", "15_plus"), ("fluctuations", "elevees"), ("capacite_perte", "elevees"),
                          ("experience", "avancee"), ("objectif", "croissance_long_terme"),
                          ("besoin_liquidite", "aucun")):
        at.selectbox(key=f"q_nouveau_{champ}").set_value(valeur).run()
    assert 'class="glc-doc"' in _textes(at)  # la politique de placement suit la fiche complète
    at.radio(key="q_nouveau_theme_ecarte_esg").set_value("exclure").run()
    assert not at.exception, at.exception

    # Portefeuille : valeur totale, puis positions ; le reste en liquidités ; refus au-delà de la valeur.
    _aller(at, "portefeuille")
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
    _aller(at, "negocier")
    at.selectbox(key="o_nouveau_ticker").set_value("AAPL").run()
    at.number_input(key="o_nouveau_montant").set_value(20_000.0).run()
    at.button(key="inspecter").click().run()
    assert not at.exception, at.exception
    carte = _verdict(at)
    assert "20 000 $" in carte and "AAPL" in carte and "10,0 %" in carte
    fiche = {"id": "nouveau", "nom": "Nouveau compte",
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


def test_explication_en_paragraphes(equipe_simulee, monkeypatch):
    import agent.inspection
    vrai = agent.inspection.inspecter

    def inspecter(*args, **options):
        r = vrai(*args, **options)
        r["explication"] = ("**Le verdict.** L'ordre est en tension. **La raison.** La pire baisse dépasse sa limite.\n"
                            "**Ce qui est possible.** Un montant plus petit serait compatible. **À savoir.** Données passées.")
        return r
    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)
    at = _demarrer()
    texte = _inspecter(at, "robert")
    bloc = next(m.value for m in at.markdown if 'class="glc-explication"' in m.value)
    assert bloc.count('<p class="t">') == 4  # un paragraphe titré par point
    assert '<p class="t">La raison</p><p>La pire baisse dépasse sa limite.</p>' in bloc
    assert '<p class="t">À savoir</p><p>Données passées.</p>' in bloc


def test_profil_la_politique_suit_la_fiche(sans_agent):
    """La fiche sous cinq rubriques, puis la politique de placement en articles numérotés, sources en bref."""
    at = _demarrer()
    _client(at, "robert", "profil")
    texte = _textes(at)
    document = next(m.value for m in at.markdown if 'class="glc-doc"' in m.value)
    for rubrique in ("Objectif", "Horizon", "Risque", "Contraintes", "Préférences"):
        assert f">{rubrique}<span>" in texte and f">{rubrique}<span>" in document
    assert "Politique de placement" in document and "profil Conservateur" in document
    # Le chemin se lit d'un coup d'œil : la fiche (1), le passage où la lumière court, la politique (2).
    assert 'class="glc-etape"><b>1</b>' in texte and 'class="glc-etape"><b>2</b>' in document
    assert 'class="glc-passage"' in texte
    numeros = [int(n) for n in __import__("re").findall(r'class="no">(\d+)<', document)]
    assert numeros == list(range(1, len(numeros) + 1)) and len(numeros) >= 8
    assert "Source : Banque Nationale" in document
    assert "questionnaire" not in document.lower() and "Hypothèse du projet" not in document
    assert "Références" in [e.label for e in at.expander]
    # Cause et effet : une réponse change, la politique change.
    at.selectbox(key="q_robert_fluctuations").set_value("elevees").run()
    at.selectbox(key="q_robert_capacite_perte").set_value("elevees").run()
    assert not at.exception, at.exception
    apres = next(m.value for m in at.markdown if 'class="glc-doc"' in m.value)
    assert "profil Conservateur" not in apres and apres != document


def test_analyse_deja_faite_et_relance(monkeypatch):
    """Une analyse rendue de mémoire le dit en une ligne ; « Relancer » redemande une analyse neuve aux agents."""
    import agent.inspection
    appels = []

    def inspecter(fiche, ticker, sens, pourcentage, operation="comptant", relancer=False):
        appels.append(relancer)
        memoire = {"statut": "nouvelle"} if relancer else {"statut": "deja_faite",
                                                          "message": "Analyse déjà faite pour cet ordre."}
        return {"explication": "**Le verdict.** En tension.", "trace": TRACE_SIMULEE, "erreur": None,
                "memoire": memoire}

    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "Analyse déjà faite pour cet ordre." in texte and appels == [False]
    at.button(key="relancer").click().run()
    assert not at.exception, at.exception
    assert appels == [False, True]
    assert "Analyse déjà faite" not in _textes(at) and not [b for b in at.button if b.key == "relancer"]
    assert "En tension" in _verdict(at)


# ---------------------------------------------------------------- introduction, choix du compte, parcours

def test_introduction_puis_choix_du_compte(sans_agent):
    from interface.textes import INTRODUCTION
    at = _ouvrir()
    assert at.session_state["etape"] == "introduction" and not at.radio  # ni navigation ni compte avant le choix
    assert "Simulation à but éducatif. Aucune transaction réelle." in _textes(at)
    assert len(INTRODUCTION) == 5
    assert INTRODUCTION[0][1].startswith("Les professionnels ont un département de risque.")  # la phrase du projet
    for n, (_, titre, lignes, note) in enumerate(INTRODUCTION):
        texte = _textes(at)
        assert f"{n + 1} / {len(INTRODUCTION)}" in texte and lignes[0] in texte and note in texte
        assert "{" not in texte.split("</style>")[-1]  # les titres qui nomment un ordre sont remplis
        vue = next(m.value for m in at.markdown if 'class="glc-vue' in m.value)
        # Chaque panneau montre une histoire dessinée qui joue seule : un SVG, ses images clés, aucune vidéo.
        assert '<svg class="film"' in vue and "<video" not in texte and "<img" not in vue
        images_cles = next(m.value for m in at.markdown if m.value.startswith("<style>@keyframes"))
        assert "infinite" in images_cles and images_cles.count("@keyframes") >= 5
        visible = __import__("re").sub(r"<style>.*?</style>", "", texte, flags=__import__("re").S)
        assert "inspect" not in visible.lower()  # le mot du produit est « analyser »
        at.button(key="intro_suivant").click().run()
        assert not at.exception, at.exception
        if n == len(INTRODUCTION) - 1:  # le dernier panneau nomme le vrai ordre prêt d'un compte enregistré
            assert "Robert veut 120 000 $ de Tesla." in texte
            assert "TSLA — Tesla" in vue and "120 000 $" in vue and "Acheter" in vue  # le vrai ordre, dessiné
    # Après le dernier panneau : le choix d'un compte, les comptes prêts d'abord, puis le nouveau compte.
    assert at.session_state["etape"] == "comptes"
    assert [b.key for b in at.button][:4] == ["compte_robert", "compte_mateo", "compte_amira", "compte_nouveau"]
    assert "prenez un compte déjà prêt" in _textes(at)
    at.button(key="compte_mateo").click().run()
    assert not at.exception, at.exception
    assert (at.session_state["etape"], at.session_state["persona"], at.session_state["page"]) == \
        ("service", "mateo", "profil")
    assert "Écrite pour Mateo, sur mesure" in _textes(at)


def test_introduction_se_passe_d_un_clic_et_se_revoit_depuis_l_aide(sans_agent):
    at = _ouvrir()
    at.button(key="passer_intro").click().run()
    assert at.session_state["etape"] == "comptes"
    at.button(key="compte_robert").click().run()
    _aller(at, "aide")
    at.button(key="revoir_intro").click().run()
    assert not at.exception, at.exception
    assert at.session_state["etape"] == "introduction"
    at.button(key="passer_intro").click().run()
    # Le compte est déjà choisi : on revient au service, sans repasser par le choix.
    assert (at.session_state["etape"], at.session_state["persona"], at.session_state["page"]) == \
        ("service", "robert", "aide")


def test_chaque_page_mene_a_la_suivante(sans_agent):
    at = _demarrer()
    for cle, page in (("suite_profil", "portefeuille"), ("suite_portefeuille", "negocier"), ("suite_negocier", "aide")):
        at.button(key=cle).click().run()
        assert not at.exception, at.exception
        assert at.session_state["page"] == page


def test_ordre_d_exemple_et_adresse_directe(sans_agent):
    at = _ouvrir()
    at.button(key="passer_intro").click().run()
    at.button(key="essayer").click().run()  # « Analyser tout de suite un ordre d'exemple »
    assert not at.exception, at.exception
    assert (at.session_state["etape"], at.session_state["page"]) == ("service", "negocier")
    assert [b for b in at.button if b.key == "inspecter"]
    # Une adresse qui nomme une page mène droit au service (essai distant, lien direct).
    direct = AppTest.from_file(APP, default_timeout=60)
    direct.query_params["page"] = "negocier"
    direct.run()
    assert not direct.exception, direct.exception
    assert direct.session_state["etape"] == "service" and [b for b in direct.button if b.key == "inspecter"]


def test_nom_du_service_et_trace_de_l_analyse(monkeypatch):
    """Le nom se lit dans une seule constante ; une analyse qui a laissé une trace montre son numéro."""
    import agent.inspection
    from interface import textes

    def inspecter(fiche, ticker, sens, pourcentage, **options):
        return {"explication": "**Le verdict.** En tension.", "trace": TRACE_SIMULEE, "erreur": None,
                "trace_aws": {"id": "a1b2c3"}}

    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)
    at = _ouvrir()
    ouverture = _textes(at)
    assert f'class="nom">{textes.NOM}<' in ouverture and textes.INTRODUCTION[0][2][0].startswith(textes.NOM)
    assert textes.SENS_DU_NOM in ouverture and "garder le cap" not in ouverture.split("</style>")[-1].lower()
    at = _demarrer()
    texte = _inspecter(at, "robert")
    assert "Analyse n° a1b2c3 · trace conservée dans Amazon S3 et CloudWatch Logs" in texte
    assert "Analyse déjà faite" not in texte
    _aller(at, "aide")
    assert "Chaque analyse laisse une trace" in _textes(at) and textes.NOM in _textes(at)


def test_films_de_l_introduction_et_vues_fixes_en_secours(sans_agent, monkeypatch):
    """Les films sont du SVG animé, sans fichier ; si un film ne peut pas être fait, la vue fixe prend sa place."""
    from interface import films, page_accueil
    from interface.textes import INTRODUCTION
    assert not list((Path(APP).parent / "interface").rglob("*.mp4"))  # aucune vidéo dans le dépôt de l'interface
    style, dessin = films.resultat([{"nom": "Risque", "note": 21.0, "decide": True}, {"nom": "Objectif", "note": None}],
                                   {"libelle": "En tension", "code": "en_tension"}, 70.0)
    assert "Angle" in dessin and "En tension" in dessin and ">21<" in dessin and "infinite" in style

    def panne(*a, **k):
        raise RuntimeError("film indisponible")

    monkeypatch.setattr(page_accueil, "_film", panne)
    at = _ouvrir()
    for _ in range(len(INTRODUCTION) - 1):
        assert '<svg class="film"' not in _textes(at) and 'class="glc-vue"' in _textes(at)
        at.button(key="intro_suivant").click().run()
        assert not at.exception, at.exception
    assert "TSLA — Tesla" in _textes(at)


def test_une_piste_n_est_montree_qu_une_fois(monkeypatch):
    """Le montant réduit testé par les agents ne double pas la ligne du moteur ; sans lui, le moteur la montre."""
    import agent.inspection

    def inspecter(fiche, ticker, sens, pourcentage, **options):
        return {"explication": "**Le verdict.** En tension.", "trace": TRACE_SIMULEE, "erreur": None,
                "pistes": [{"famille": "montant_reduit", "libelle_famille": "Montant plus petit",
                            "ordres": [{"ticker": ticker, "sens": sens, "pourcentage": 7.0}],
                            "raison": "Réduire la taille pour ramener la pire année sous sa limite.",
                            "verdict": {"code": "compatible", "libelle": "Compatible"}},
                           {"famille": "autre_instrument", "libelle_famille": "Autre instrument",
                            "ordres": [{"ticker": "AAPL", "sens": sens, "pourcentage": pourcentage}],
                            "raison": "Un titre établi.", "verdict": {"code": "compatible", "libelle": "Compatible"}}]}

    monkeypatch.setattr(agent.inspection, "inspecter", inspecter)
    at = _demarrer()
    texte = _inspecter(at, "robert")
    tableau = next(m.value for m in at.markdown if "Piste testée" in m.value)
    assert tableau.count("Achat de 56 000 $ de TSLA") == 1 and tableau.count("<tr>") == 3  # l'en-tête et deux pistes
    assert "Montant plus petit" in tableau and "<b>Montant réduit</b>" not in tableau
    assert "Pour devenir compatible : 56 000 $ ou moins" in texte


def test_les_deux_atouts_dans_l_introduction_et_l_aide(sans_agent):
    """L'équipe d'agents et le modèle de notation se lisent dès l'introduction, puis dans l'aide ; jamais « score »."""
    from interface import textes
    mots = " ".join(t + " " + " ".join(lignes) + " " + note for _, t, lignes, note in textes.INTRODUCTION).lower()
    assert "équipe d'agents" in mots and "modèle de notation" in mots and "note sur 100" in mots
    assert "score" not in mots and "garder le cap" not in mots
    at = _demarrer()
    _aller(at, "aide")
    aide = _textes(at)
    assert "Les professionnels ont un département de risque." in aide and "Une équipe de deux agents d'IA" in aide
    for service in ("Amazon CloudWatch Logs", "AWS IAM", "AWS Systems Manager", "la trace de chaque analyse"):
        assert service in aide
    assert "contrôle d'ancrage (Amazon Bedrock Guardrails)" in aide
