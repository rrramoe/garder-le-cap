"""Agent : outils, trace, chargement des identifiants, et test d'acceptation 6 sur Bedrock.

Les essais hors ligne remplacent Bedrock par un modèle simulé qui joue un scénario d'appels.
Le test 6 appelle le vrai Bedrock ; il est sauté sans identifiants AWS (ou avec GLC_SANS_AWS=1).
"""
import json
import os

import pytest
from strands.models.model import Model

from agent import identifiants, inspection
from agent.outils import NOMS_OUTILS, creer_outils
from moteur import api, donnees

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)

CHAMPS = {"explication", "trace", "modele", "duree_s", "erreur", "garde_fou", "ancrage", "substitut", "pistes", "intention",
          "agents", "correction"}
CHAMPS_ETAPE = {"etape", "outil", "arguments", "resultat_resume", "resultat", "agent"}
MOTS_INTERDITS = ("bonne idée", "mauvaise idée", "je recommande", "je conseille")


# --- Modèle simulé ------------------------------------------------------------------------------

class ModeleSimule(Model):
    """Joue une liste de tours : chaque tour est une liste d'appels d'outils, ou un texte final."""

    def __init__(self, tours, raisonnement="Je réfléchis avant de répondre.", erreur=None):
        self.tours, self.raisonnement, self.erreur, self.appels = list(tours), raisonnement, erreur, 0
        self.config = {"model_id": "modele-simule"}

    def update_config(self, **config):
        self.config.update(config)

    def get_config(self):
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        if self.erreur is not None:
            raise self.erreur
        tour = self.tours[min(self.appels, len(self.tours) - 1)]
        self.appels += 1
        yield {"messageStart": {"role": "assistant"}}
        if self.raisonnement:
            yield {"contentBlockDelta": {"delta": {"reasoningContent": {"text": self.raisonnement}}}}
            yield {"contentBlockDelta": {"delta": {"reasoningContent": {"signature": "sig"}}}}
            yield {"contentBlockStop": {}}
        if isinstance(tour, str):
            yield {"contentBlockDelta": {"delta": {"text": tour}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        for i, (nom, arguments) in enumerate(tour):
            yield {"contentBlockStart": {"start": {"toolUse": {"name": nom, "toolUseId": f"t{self.appels}-{i}"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}


ORDRE_ROBERT = {"client_id": "robert", "ticker": "TSLA", "sens": "achat", "pourcentage": 15}
SCENARIO_ROBERT = [
    [("lire_fiche_client", {"client_id": "robert"})],
    [("lire_fiche_instrument", {"ticker": "TSLA"})],
    [("simuler_ordre", ORDRE_ROBERT)],
    [("chercher_taille_compatible", ORDRE_ROBERT)],
    "**Verdict** : en tension.",
]


# --- Outils -------------------------------------------------------------------------------------

def test_outils_noms_snake_case():
    outils = creer_outils("robert")
    assert tuple(o.tool_name for o in outils) == NOMS_OUTILS
    assert all(n.isascii() and n == n.lower() for n in NOMS_OUTILS)


def test_outils_enveloppent_le_moteur():
    o = {t.tool_name: t for t in creer_outils("robert")}
    assert o["lire_fiche_client"]("robert") == api.lire_fiche_client("robert")
    assert o["lire_fiche_instrument"]("TSLA") == api.lire_fiche_instrument("TSLA")
    assert o["simuler_ordre"]("robert", "TSLA", "achat", 15) == api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert o["chercher_taille_compatible"]("robert", "TSLA", "achat", 15) == \
        api.chercher_taille_compatible("robert", "TSLA", "achat", 15)
    assert o["lister_instruments"]("actions") == api.lister_instruments("actions")


def test_outils_utilisent_la_fiche_modifiee():
    fiche = {"persona": "robert", "questionnaire": {"horizon": "15_plus"}}
    o = {t.tool_name: t for t in creer_outils(fiche)}
    assert o["lire_fiche_client"]("robert")["deduit"]["horizon_annees"]["valeur"] == 15
    assert o["simuler_ordre"]("Robert", "TSLA", "achat", 15) == api.simuler_ordre(fiche, "TSLA", "achat", 15)
    assert api.lire_fiche_client("robert")["deduit"]["horizon_annees"]["valeur"] == 3


def test_outils_passent_l_operation():
    fiche = {"persona": "robert", "questionnaire": {"experience": "intermediaire"}}
    o = {t.tool_name: t for t in creer_outils(fiche)}
    assert o["simuler_ordre"]("robert", "TSLA", "vente", 5, "decouvert") == \
        api.simuler_ordre(fiche, "TSLA", "vente", 5, "decouvert")
    assert o["chercher_taille_compatible"]("robert", "TSLA", "vente", 5, "decouvert") == \
        api.chercher_taille_compatible(fiche, "TSLA", "vente", 5, "decouvert")
    assert "Vente à découvert" in inspection.resumer("simuler_ordre", api.simuler_ordre(fiche, "TSLA", "vente", 5,
                                                                                          "decouvert"))


def test_consigne_nomme_l_operation():
    assert "operation" not in inspection.consigne("robert", "TSLA", "achat", 15)
    texte = inspection.consigne("robert", "TSLA", "vente", 5, "decouvert")
    assert "vente à découvert" in texte and 'operation="decouvert"' in texte


def test_outils_refusent_un_autre_client():
    o = {t.tool_name: t for t in creer_outils("robert")}
    assert "erreur" in o["simuler_ordre"]("mateo", "XOM", "achat", 8)


# --- Trace et entrée de l'agent (modèle simulé) ------------------------------------------------

def test_inspecter_trace_et_explication_avec_modele_simule():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert set(r) == CHAMPS
    assert r["erreur"] is None
    assert r["explication"] == "**Verdict** : en tension."          # le raisonnement est écarté
    assert r["modele"] == "modele-simule" and r["duree_s"] >= 0
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre",
                                                "chercher_taille_compatible"]
    assert [e["etape"] for e in r["trace"]] == [1, 2, 3, 4]
    assert all(set(e) == CHAMPS_ETAPE for e in r["trace"])
    assert r["trace"][2]["arguments"] == ORDRE_ROBERT
    assert r["trace"][2]["resultat"] == api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert r["trace"][2]["resultat_resume"].startswith("Verdict : En tension")
    assert "11,5 %" in r["trace"][3]["resultat_resume"]
    json.dumps(r)


SCENARIO_SUBSTITUT = SCENARIO_ROBERT[:4] + [
    [("lister_instruments", {"classe": "actions"})],
    [("simuler_ordre", {**ORDRE_ROBERT, "ticker": "SPY"})],
    "**Verdict** : en tension. **Ce qui est possible** : un ordre de même taille sur SPY serait compatible.",
]


def test_substitut_dans_la_trace_et_le_resultat():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT), equipe=False)
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre",
                                                "chercher_taille_compatible", "lister_instruments", "simuler_ordre"]
    assert r["trace"][5]["resultat_resume"].startswith("Substitut testé (SPY) : Verdict : Compatible")
    assert not r["trace"][2]["resultat_resume"].startswith("Substitut")
    s = r["substitut"]
    assert s["ticker"] == "SPY" and s["verdict"]["code"] == "compatible" and s["etape"] == 6
    assert s["nature"] == "possibilite_testee" and "pas une recommandation" in s["avertissement"]
    assert s["score"] == api.simuler_ordre("robert", "SPY", "achat", 15)["score"]


def test_pas_de_substitut_sans_autre_symbole():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert r["substitut"] is None


def test_resumes_en_francais_correct():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT), equipe=False)
    resumes = " ".join(e["resultat_resume"] for e in r["trace"])
    assert "détail détaillé" in resumes and "étiquettes : spéculatif" in resumes
    assert "compatible avec ajustement" in resumes and "ampleur de la pire baisse" in resumes
    for identifiant in ("detaille", "speculatif", "compatible_avec_ajustement", "plus_grosse_action", "ecarte_esg"):
        assert identifiant not in resumes, identifiant


def test_prompt_systeme_cadre():
    texte = inspection.PROMPT_SYSTEME.read_text(encoding="utf-8")
    assert "180" in texte and "lister_instruments" in texte and "pas une recommandation" in texte
    assert "inspection" not in texte.lower()  # vocabulaire de l'interface : « analyse »


def test_prompts_de_l_equipe_cadres():
    from agent.explorateur import PROMPT_EXPLORATEUR
    principal = inspection.PROMPT_PRINCIPAL.read_text(encoding="utf-8")
    explorateur = PROMPT_EXPLORATEUR.read_text(encoding="utf-8")
    assert "180" in principal and "envoyer_explorateur" in principal and "possibilité testée" in principal
    assert "objectif" in principal and "horizon" in principal
    for outil in ("chercher_taille_compatible", "lister_instruments", "simuler_scenario"):
        assert outil in explorateur and outil not in principal
    assert "Finalité supposée :" in explorateur and "jamais plus que l'achat" in explorateur
    assert "combinaison" in explorateur and "lire_fiche_client" in explorateur
    for texte in (principal, explorateur):
        assert "inspection" not in texte.lower()


def test_trace_garde_l_ordre_des_appels_paralleles():
    scenario = [[("lire_fiche_client", {"client_id": "mateo"}), ("lire_fiche_instrument", {"ticker": "XOM"})],
                [("simuler_ordre", {"client_id": "mateo", "ticker": "XOM", "sens": "achat", "pourcentage": 8})],
                "Incompatible."]
    r = inspection.inspecter("mateo", "XOM", "achat", 8, modele=ModeleSimule(scenario, raisonnement=None), equipe=False)
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"]
    assert "Contrainte stricte violée : écarté ESG" in r["trace"][2]["resultat_resume"]
    assert "contraintes strictes : écarté ESG" in r["trace"][0]["resultat_resume"]


def test_limite_de_tours():
    boucle = [[("lire_fiche_instrument", {"ticker": "TSLA"})]]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(boucle), equipe=False)
    assert r["explication"] is None and r["erreur"]
    assert 1 <= len(r["trace"]) <= inspection.LIMITE_TOURS


def test_inspecter_ne_leve_jamais():
    from botocore.exceptions import ClientError
    e = ClientError({"Error": {"Code": "ExpiredTokenException",
                               "Message": "arn:aws:sts::123456789012:assumed-role/x expired"}}, "ConverseStream")
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule([], erreur=e), equipe=False)
    assert set(r) == CHAMPS
    assert r["explication"] is None and r["trace"] == []
    assert "expirés" in r["erreur"] and "arn:" not in r["erreur"] and "123456789012" not in r["erreur"]


def test_extraire_trace_resultat_manquant_ou_en_erreur():
    messages = [
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "a", "name": "lire_fiche_instrument",
                                                       "input": {"ticker": "XYZ"}}},
                                          {"toolUse": {"toolUseId": "b", "name": "simuler_ordre", "input": {}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "a", "status": "error",
                                                     "content": [{"text": "Instrument inconnu"}]}}]},
    ]
    t = inspection.extraire_trace(messages)
    assert t[0]["resultat"] == {"erreur": "Instrument inconnu"} and t[0]["resultat_resume"].startswith("Erreur")
    assert t[1]["resultat"] is None and "interrompu" in t[1]["resultat_resume"]


# --- Identifiants -------------------------------------------------------------------------------

def test_identifiants_lus_depuis_le_fichier(tmp_path, monkeypatch):
    f = tmp_path / "datathon.env"
    f.write_text("export AWS_ACCESS_KEY_ID=CLE\nexport AWS_SECRET_ACCESS_KEY='SECRET'\n"
                 "export AWS_SESSION_TOKEN=\"JETON=\"\n# commentaire\nAUTRE=1\n", encoding="utf-8")
    for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AUTRE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("GLC_AWS_ENV", str(f))
    assert identifiants.charger_identifiants() is True
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "SECRET" and os.environ["AWS_SESSION_TOKEN"] == "JETON="
    assert "AUTRE" not in os.environ


def test_identifiants_de_l_environnement_gardes(tmp_path, monkeypatch):
    f = tmp_path / "datathon.env"
    f.write_text("export AWS_ACCESS_KEY_ID=FICHIER\nexport AWS_SECRET_ACCESS_KEY=FICHIER\n", encoding="utf-8")
    monkeypatch.setenv("GLC_AWS_ENV", str(f))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ENV")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ENV")
    identifiants.charger_identifiants()
    assert os.environ["AWS_ACCESS_KEY_ID"] == "ENV"


# --- Test d'acceptation 6 : vrai Bedrock -------------------------------------------------------

def _aws_disponible() -> bool:
    return os.environ.get("GLC_SANS_AWS") != "1" and identifiants.identifiants_disponibles()


bedrock = pytest.mark.skipif(not _aws_disponible(), reason="identifiants AWS absents : test 6 sauté")


def _sous_suite(attendu, obtenu) -> bool:
    it = iter(obtenu)
    return all(any(o == a for o in it) for a in attendu)


def _verifier_rapport(r):
    assert set(r) == CHAMPS
    assert r["erreur"] is None, r["erreur"]
    assert r["explication"]
    texte = r["explication"].lower()
    assert not any(m in texte for m in MOTS_INTERDITS)


@bedrock
def test_6_cas_1_robert_tsla_cherche_la_taille():
    # Équipe : le chef de dossier lit, simule, puis envoie l'explorateur, qui fait la recherche.
    r = inspection.inspecter("robert", "TSLA", "achat", 15)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "envoyer_explorateur"],
                       outils), outils
    assert r["agents"][1]["statut"] == "termine" and r["pistes"], r["agents"]
    assert all(e["agent"] == "explorateur" for e in r["trace"] if e["outil"] in
               ("chercher_taille_compatible", "simuler_scenario", "lister_instruments"))


def _mots(texte: str) -> int:
    import re
    return len(re.findall(r"[\w’'-]*\w", texte))


@bedrock
def test_6_cas_1_pistes_et_longueur():
    r = inspection.inspecter("robert", "TSLA", "achat", 15)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert outils[:4] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "envoyer_explorateur"]
    assert 2 <= len(r["pistes"]) <= 4 and all(p["raison"] for p in r["pistes"]), r["pistes"]
    assert r["intention"]
    assert _mots(r["explication"]) <= 180
    assert "recommand" not in r["explication"].lower()


@bedrock
def test_6_cas_2_mateo_xom_ne_cherche_pas_de_taille():
    r = inspection.inspecter("mateo", "XOM", "achat", 8)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"], outils), outils
    assert "envoyer_explorateur" not in outils and "chercher_taille_compatible" not in outils
    assert r["pistes"] == [] and r["substitut"] is None  # chemin visiblement différent du cas 1
    assert _mots(r["explication"]) <= 180


@bedrock
def test_decouvert_debutante_ne_cherche_pas_de_taille():
    fiche = {"persona": "robert", "questionnaire": {"experience": "debutante"}}
    r = inspection.inspecter(fiche, "TSLA", "vente", 5, operation="decouvert")
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"], outils), outils
    assert "chercher_taille_compatible" not in outils and "envoyer_explorateur" not in outils
    simulation = next(e for e in r["trace"] if e["outil"] == "simuler_ordre")
    assert simulation["arguments"].get("operation") == "decouvert"
    assert simulation["resultat"]["verdict"]["code"] == "incompatible"
    assert len(r["explication"].split()) <= 200  # limite de 180 mots dans le prompt, marge pour les marqueurs **


# --- Suivi en direct des étapes ------------------------------------------------------------------

def test_suivi_des_etapes_avec_modele_simule():
    evenements = []
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT), equipe=False,
                             sur_etape=evenements.append)
    assert r["erreur"] is None
    assert all(e["agent"] == "principal" for e in evenements)
    moments = [e["moment"] for e in evenements]
    assert moments[-3:] == ["redaction", "verification", "fin"]
    debuts = [e for e in evenements if e["moment"] == "debut_outil"]
    fins = [e for e in evenements if e["moment"] == "fin_outil"]
    assert [e["outil"] for e in debuts] == [e["outil"] for e in r["trace"]]
    assert [e["etape"] for e in debuts] == [1, 2, 3, 4, 5, 6] == [e["etape"] for e in fins]
    assert debuts[0]["libelle"] == "Je lis votre fiche." and debuts[2]["arguments"] == ORDRE_ROBERT
    assert "SPY" in debuts[5]["libelle"]
    assert [e["resultat_resume"] for e in fins] == [e["resultat_resume"] for e in r["trace"]]
    for e in evenements:
        assert set(e) <= {"moment", "agent", "etape", "outil", "arguments", "libelle", "resultat_resume"}
        assert e["moment"] != "debut_outil" or e["libelle"].endswith(".")


def test_suivi_qui_leve_ne_casse_pas_l_analyse():
    def casse(evenement):
        raise RuntimeError("affichage en panne")
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False, sur_etape=casse)
    assert r["erreur"] is None and r["explication"] == "**Verdict** : en tension." and len(r["trace"]) == 4


# --- Pistes testées (construites par le code) ---------------------------------------------------

PARTAGE = [{"ticker": "TSLA", "sens": "achat", "pourcentage": 7.5}, {"ticker": "XIU.TO", "sens": "achat", "pourcentage": 7.5}]
FINANCE = [{"ticker": "TSLA", "sens": "achat", "pourcentage": 15}, {"ticker": "XBB.TO", "sens": "vente", "pourcentage": 10}]
SCENARIO_PISTES = SCENARIO_ROBERT[:4] + [
    [("lister_instruments", {"classe": "actions"})],
    [("simuler_ordre", {**ORDRE_ROBERT, "ticker": "SPY"})],
    [("simuler_scenario", {"client_id": "robert", "ordres": PARTAGE})],
    [("simuler_scenario", {"client_id": "robert", "ordres": FINANCE})],
    "**Verdict** : en tension.",
]


def test_outil_simuler_scenario():
    o = {t.tool_name: t for t in creer_outils("robert")}
    assert o["simuler_scenario"]("robert", PARTAGE) == api.simuler_scenario("robert", PARTAGE)
    assert "erreur" in o["simuler_scenario"]("mateo", PARTAGE)


def test_pistes_construites_depuis_les_resultats_des_outils():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_PISTES), equipe=False)
    pistes = r["pistes"]
    assert [p["famille"] for p in pistes] == ["montant_reduit", "autre_instrument", "achat_partage",
                                              "vente_pour_financer"]
    assert [p["etape"] for p in pistes] == [4, 6, 7, 8]
    taille = api.chercher_taille_compatible("robert", "TSLA", "achat", 15)
    assert pistes[0]["ordres"] == [{"ticker": "TSLA", "sens": "achat", "pourcentage": taille["taille_compatible_pct"]}]
    assert pistes[0]["verdict"]["code"] == "compatible" and pistes[0]["score"] >= 50
    assert pistes[0]["direction"]["cas"] == "reste_dans_la_politique"
    spy = api.simuler_ordre("robert", "SPY", "achat", 15)
    assert pistes[1]["score"] == spy["score"] and pistes[1]["verdict"]["code"] == spy["verdict"]["code"]
    assert pistes[1]["direction"]["cas"] == spy["direction"]["cas"] and "SPY" in pistes[1]["description"]
    for p, ordres in ((pistes[2], PARTAGE), (pistes[3], FINANCE)):
        s = api.simuler_scenario("robert", ordres)
        assert p["score"] == s["score"] and p["verdict"]["code"] == s["verdict"]["code"]
        assert [o["ticker"] for o in p["ordres"]] == [o["ticker"] for o in ordres]
    assert "payé en partie par la vente de 10 % de XBB.TO" in pistes[3]["description"]
    assert all(set(p) == {"famille", "libelle_famille", "description", "ordres", "raison", "verdict", "score",
                          "direction", "etape"} for p in pistes)
    assert r["substitut"]["ticker"] == "SPY"                     # le champ existant reste cohérent
    assert r["trace"][6]["resultat_resume"].startswith("Scénario : achat de 7,5 % de TSLA, achat de 7,5 % de XIU.TO.")
    json.dumps(r)


def test_pas_de_piste_pour_l_ordre_lui_meme_ni_pour_une_erreur():
    scenario = SCENARIO_ROBERT[:3] + [
        [("simuler_scenario", {"client_id": "robert", "ordres": [{"ticker": "RY.TO", "sens": "achat", "pourcentage": 15},
                                                                  {"ticker": "SPY", "sens": "achat", "pourcentage": 5}]})],
        "Texte."]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(scenario), equipe=False)
    assert r["pistes"] == []
    assert inspection.inspecter("mateo", "XOM", "achat", 8, modele=ModeleSimule(
        [[("simuler_ordre", {"client_id": "mateo", "ticker": "XOM", "sens": "achat", "pourcentage": 8})], "X."]),
        equipe=False)["pistes"] == []


def test_montant_plus_petit_sans_taille_compatible():
    trace = [{"etape": 1, "outil": "simuler_ordre", "arguments": {}, "resultat": api.simuler_ordre("robert", "BTC-USD", "achat", 5)},
             {"etape": 2, "outil": "chercher_taille_compatible", "arguments": {},
              "resultat": api.chercher_taille_compatible("robert", "BTC-USD", "achat", 5)}]
    p = inspection.extraire_pistes(trace, "BTC-USD", "achat", 5)
    if trace[1]["resultat"]["taille_compatible_pct"] is None:
        assert p[0]["verdict"]["code"] == "en_tension" and p[0]["description"].startswith("Aucun montant compatible")
    else:
        assert p[0]["verdict"]["code"] == "compatible"


# --- Équipe de deux agents (modèles simulés) -----------------------------------------------------

MISSION = "Le risque de baisse dépasse la limite du profil prudent ; Robert évite le spéculatif."
PRINCIPAL_ROBERT = SCENARIO_ROBERT[:3] + [
    [("envoyer_explorateur", {"client_id": "robert", "mission": MISSION})],
    "**Verdict** : en tension.",
]
EXPLORATEUR_ROBERT = [
    [("chercher_taille_compatible", {**ORDRE_ROBERT, "raison": "La pire baisse vient de la taille de l'achat."})],
    [("simuler_scenario", {"client_id": "robert", "ordres": PARTAGE,
                           "raison": "Garder un peu de TSLA, le reste dans un fonds d'actions canadiennes."})],
    "Finalité supposée : l'ordre semble chercher une exposition à une action de croissance.\n"
    "Cause : la pire baisse du portefeuille dépasserait la limite du profil.\n"
    "Pistes retenues : 1, 2\n"
    "Bilan : un montant plus petit et un achat partagé ont été testés.",
]


def test_equipe_chef_de_dossier_et_explorateur():
    evenements = []
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(PRINCIPAL_ROBERT), equipe=True,
                             modele_explorateur=ModeleSimule(EXPLORATEUR_ROBERT), sur_etape=evenements.append)
    assert set(r) == CHAMPS and r["erreur"] is None
    assert [(e["agent"], e["outil"]) for e in r["trace"]] == [
        ("principal", "lire_fiche_client"), ("principal", "lire_fiche_instrument"), ("principal", "simuler_ordre"),
        ("principal", "envoyer_explorateur"), ("explorateur", "chercher_taille_compatible"),
        ("explorateur", "simuler_scenario")]
    assert [e["etape"] for e in r["trace"]] == [1, 2, 3, 4, 5, 6]
    assert [p["famille"] for p in r["pistes"]] == ["montant_reduit", "achat_partage"]
    assert r["pistes"][1]["raison"].startswith("Garder un peu de TSLA") and r["pistes"][1]["etape"] == 6
    assert r["pistes"][1]["score"] == api.simuler_scenario("robert", PARTAGE)["score"]
    assert r["intention"].startswith("l'ordre semble chercher")
    principal, explorateur = r["agents"]
    assert principal["nom"] == "principal" and principal["etapes"] == [1, 2, 3, 4]
    assert explorateur["statut"] == "termine" and explorateur["mission"] == MISSION and explorateur["etapes"] == [5, 6]
    retour = r["trace"][3]["resultat"]
    assert retour["statut"] == "termine" and len(retour["pistes"]) == 2 and retour["cause"]["mesure"] == "ampleur"
    assert r["trace"][3]["resultat_resume"].startswith("Explorateur revenu avec 2 piste(s)")
    debuts = [(e["agent"], e["etape"], e["outil"]) for e in evenements if e["moment"] == "debut_outil"]
    assert debuts == [("principal", 1, "lire_fiche_client"), ("principal", 2, "lire_fiche_instrument"),
                      ("principal", 3, "simuler_ordre"), ("principal", 4, "envoyer_explorateur"),
                      ("explorateur", 5, "chercher_taille_compatible"), ("explorateur", 6, "simuler_scenario")]
    assert {e["agent"] for e in evenements} == {"principal", "explorateur"}
    assert [e["moment"] for e in evenements][-2:] == ["verification", "fin"]
    json.dumps(r)


def test_explorateur_refuse_hors_tension():
    for client, ticker, pct, motif in (("mateo", "XOM", 8, "contrainte stricte"), ("robert", "XIU.TO", 2, "déjà compatible")):
        ordre = {"client_id": client, "ticker": ticker, "sens": "achat", "pourcentage": pct}
        principal = [[("lire_fiche_client", {"client_id": client})], [("simuler_ordre", ordre)],
                     [("envoyer_explorateur", {"client_id": client, "mission": "Cherche."})], "Texte."]
        explorateur = ModeleSimule(EXPLORATEUR_ROBERT)
        r = inspection.inspecter(client, ticker, "achat", pct, modele=ModeleSimule(principal), equipe=True,
                                 modele_explorateur=explorateur)
        assert explorateur.appels == 0 and r["pistes"] == [] and r["intention"] is None
        assert motif in r["trace"][2]["resultat"]["erreur"]
        assert r["agents"][1]["statut"] == "non_envoye" and motif in r["agents"][1]["avis"]


def test_explorateur_envoye_une_seule_fois():
    principal = PRINCIPAL_ROBERT[:4] + [[("envoyer_explorateur", {"client_id": "robert", "mission": "Encore."})],
                                        "Texte."]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(principal), equipe=True,
                             modele_explorateur=ModeleSimule(EXPLORATEUR_ROBERT))
    envois = [e for e in r["trace"] if e["outil"] == "envoyer_explorateur"]
    assert len(envois) == 2 and "déjà été envoyé" in envois[1]["resultat"]["erreur"]
    assert len(r["pistes"]) == 2


def test_explorateur_en_echec_repli_sur_la_taille_du_code():
    from botocore.exceptions import ClientError
    e = ClientError({"Error": {"Code": "ThrottlingException", "Message": "trop"}}, "ConverseStream")
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(PRINCIPAL_ROBERT), equipe=True,
                             modele_explorateur=ModeleSimule([], erreur=e))
    assert r["erreur"] is None and r["agents"][1]["statut"] == "repli"
    assert "taille compatible calculée par le code" in r["agents"][1]["avis"]
    taille = api.chercher_taille_compatible("robert", "TSLA", "achat", 15)
    assert [p["famille"] for p in r["pistes"]] == ["montant_reduit"]
    assert r["pistes"][0]["ordres"][0]["pourcentage"] == taille["taille_compatible_pct"]
    assert r["trace"][3]["resultat"]["statut"] == "repli"


class ModeleLent(ModeleSimule):
    async def stream(self, *args, **kwargs):
        import asyncio
        await asyncio.sleep(3)
        async for x in super().stream(*args, **kwargs):
            yield x


def test_explorateur_trop_lent_repli(monkeypatch):
    from agent import explorateur
    monkeypatch.setattr(explorateur, "DELAI_EXPLORATEUR_S", 0.5)
    evenements = []
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(PRINCIPAL_ROBERT), equipe=True,
                             modele_explorateur=ModeleLent(EXPLORATEUR_ROBERT), sur_etape=evenements.append)
    assert r["agents"][1]["statut"] == "repli" and "délai" in r["agents"][1]["raison_du_repli"]
    assert [p["famille"] for p in r["pistes"]] == ["montant_reduit"]


def test_explorateur_borne_a_six_essais_numerotes():
    from agent.outils import NOMS_OUTILS_EXPLORATEUR, creer_outils_explorateur
    outils = creer_outils_explorateur("robert")
    assert tuple(t.tool_name for t in outils) == NOMS_OUTILS_EXPLORATEUR
    o = {t.tool_name: t for t in outils}
    assert "erreur" in o["simuler_ordre"]("robert", "SPY", "achat", 50, "trop gros")       # une erreur ne compte pas
    for n, ticker in enumerate(("SPY", "XIU.TO", "QQQ", "AGG", "GLD"), start=1):
        assert o["simuler_ordre"]("robert", ticker, "achat", 5, "essai")["essai"] == n
    assert o["simuler_scenario"]("robert", PARTAGE, "essai")["essai"] == 6
    assert "Limite de 6 essais" in o["chercher_taille_compatible"]("robert", "TSLA", "achat", 15, "essai")["erreur"]


def test_compte_rendu_de_l_explorateur():
    from agent.explorateur import lire_compte_rendu
    cr = lire_compte_rendu("**Finalité supposée** : une banque.\nCause : le plafond.\nPistes retenues : 1, 3 et 5\n"
                           "Bilan : deux pistes.")
    assert cr == {"intention": "une banque.", "cause": "le plafond.", "retenues": [1, 3, 5], "bilan": "deux pistes."}
    assert lire_compte_rendu(None) == {"intention": None, "cause": None, "retenues": None, "bilan": None}


def test_pistes_retenues_par_l_explorateur():
    from agent.explorateur import retenir
    pistes = [(n, {"n": n}) for n in range(1, 7)]
    assert retenir(pistes, [2, 5]) == [{"n": 2}, {"n": 5}]
    assert retenir(pistes, [1, 2, 3, 4, 5]) == [{"n": n} for n in (1, 2, 3, 4)]
    assert retenir(pistes, None) == [{"n": n} for n in (3, 4, 5, 6)]
    assert retenir(pistes, [9]) == [{"n": n} for n in (3, 4, 5, 6)]


def test_familles_combinees():
    reduit_et_complement = [{"ticker": "TSLA", "sens": "achat", "pourcentage": 6},
                            {"ticker": "SPY", "sens": "achat", "pourcentage": 4}]
    partage_paye = [{"ticker": "TSLA", "sens": "achat", "pourcentage": 7.5},
                    {"ticker": "XIU.TO", "sens": "achat", "pourcentage": 7.5},
                    {"ticker": "XBB.TO", "sens": "vente", "pourcentage": 5}]
    trace = [{"etape": 1, "outil": "simuler_ordre", "arguments": {}, "resultat": api.simuler_ordre("robert", "TSLA", "achat", 15)}]
    for i, ordres in enumerate((reduit_et_complement, partage_paye), start=2):
        trace.append({"etape": i, "outil": "simuler_scenario", "arguments": {"ordres": ordres, "raison": "r"},
                      "resultat": api.simuler_scenario("robert", ordres)})
    p = inspection.extraire_pistes(trace, "TSLA", "achat", 15)
    assert [x["famille"] for x in p] == ["combinaison", "combinaison"]
    assert p[0]["description"].startswith("Montant plus petit avec un complément")
    assert "payé en partie par la vente de 5 % de XBB.TO" in p[1]["description"] and p[1]["raison"] == "r"


def test_reglage_agent_seul():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert [a["nom"] for a in r["agents"]] == ["principal"] and r["intention"] is None
    assert [e["outil"] for e in r["trace"]][3] == "chercher_taille_compatible"


def test_redaction_annoncee_au_texte_final_seulement():
    scenario = [[("lire_fiche_client", {"client_id": "robert"})], "**Verdict** : en tension."]
    evenements = []

    class Bavard(ModeleSimule):
        """Écrit une phrase avant son appel d'outil, comme le fait parfois le vrai modèle."""
        async def stream(self, *args, **kwargs):
            if self.appels == 0:
                yield {"messageStart": {"role": "assistant"}}
                yield {"contentBlockDelta": {"delta": {"text": "Je commence par lire la fiche."}}}
                yield {"contentBlockStop": {}}
                self.appels += 1
                yield {"contentBlockStart": {"start": {"toolUse": {"name": "lire_fiche_client", "toolUseId": "t0"}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({"client_id": "robert"})}}}}
                yield {"contentBlockStop": {}}
                yield {"messageStop": {"stopReason": "tool_use"}}
                return
            async for x in super().stream(*args, **kwargs):
                yield x

    inspection.inspecter("robert", "TSLA", "achat", 15, modele=Bavard(scenario), equipe=False,
                         sur_etape=evenements.append)
    moments = [e["moment"] for e in evenements]
    assert moments.count("redaction") == 1 and moments.index("redaction") > moments.index("fin_outil")


# --- Correction de son texte après vérification --------------------------------------------------

def test_correction_apres_un_chiffre_faux():
    scenario = SCENARIO_ROBERT + ["**Verdict** : en tension, avec un score de 39,6."]
    scenario[4] = "**Verdict** : en tension, avec un score de 97,3."
    evenements = []
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(scenario), equipe=False,
                             sur_etape=evenements.append)
    assert r["correction"]["faite"] and r["correction"]["reussie"]
    assert r["correction"]["motifs"] == ["Le chiffre 97,3 ne figure dans aucun résultat d'outil."]
    assert r["explication"] == "**Verdict** : en tension, avec un score de 39,6."
    assert r["ancrage"]["chiffres_non_sources"] == []
    assert r["trace"][-1]["outil"] == "corriger_le_texte" and r["trace"][-1]["agent"] == "principal"
    assert r["trace"][-1]["resultat_resume"] == "L'agent a corrigé son texte après vérification."
    moments = [e["moment"] for e in evenements]
    assert moments[-5:] == ["redaction", "verification", "correction", "verification", "fin"]


def test_correction_une_seule_fois():
    scenario = SCENARIO_ROBERT + ["**Verdict** : score 12,3."]
    scenario[4] = "**Verdict** : score 97,3."
    modele = ModeleSimule(scenario)
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=modele, equipe=False)
    assert r["correction"]["faite"] and not r["correction"]["reussie"]
    assert r["ancrage"]["statut"] == "non_appuyee" and "12,3" in r["ancrage"]["message"]   # l'avis reste
    assert modele.appels == 6                                                             # 5 tours + 1 réécriture


def test_pas_de_correction_quand_le_texte_est_juste():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert r["correction"] == {"faite": False, "motifs": []}
    assert all(e["outil"] != "corriger_le_texte" for e in r["trace"])


def test_explorateur_a_l_outil_decrire_apport():
    from agent.outils import creer_outils_explorateur
    o = {t.tool_name: t for t in creer_outils_explorateur("robert")}
    assert o["decrire_apport"]("robert", "TSLA", 15) == api.decrire_apport("robert", "TSLA", 15)
    assert "erreur" in o["decrire_apport"]("mateo", "TSLA", 15)
    from agent.suivi import libelle_outil
    assert libelle_outil("decrire_apport", {"ticker": "TSLA"}) == "Je regarde ce que TSLA apporterait à votre portefeuille."



def test_correction_d_un_texte_trop_long():
    long = "**Verdict** : en tension. " + "mot " * 200
    scenario = SCENARIO_ROBERT[:4] + [long, "**Verdict** : en tension."]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(scenario), equipe=False)
    assert r["correction"]["faite"] and r["correction"]["reussie"]
    assert "la limite absolue est de 180 mots" in r["correction"]["motifs"][0]
    assert r["explication"] == "**Verdict** : en tension."
