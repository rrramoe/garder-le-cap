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

CHAMPS = {"explication", "trace", "modele", "duree_s", "erreur", "garde_fou", "ancrage", "substitut", "pistes"}
CHAMPS_ETAPE = {"etape", "outil", "arguments", "resultat_resume", "resultat"}
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
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT))
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
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT))
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre",
                                                "chercher_taille_compatible", "lister_instruments", "simuler_ordre"]
    assert r["trace"][5]["resultat_resume"].startswith("Substitut testé (SPY) : Verdict : Compatible")
    assert not r["trace"][2]["resultat_resume"].startswith("Substitut")
    s = r["substitut"]
    assert s["ticker"] == "SPY" and s["verdict"]["code"] == "compatible" and s["etape"] == 6
    assert s["nature"] == "possibilite_testee" and "pas une recommandation" in s["avertissement"]
    assert s["score"] == api.simuler_ordre("robert", "SPY", "achat", 15)["score"]


def test_pas_de_substitut_sans_autre_symbole():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT))
    assert r["substitut"] is None


def test_resumes_en_francais_correct():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT))
    resumes = " ".join(e["resultat_resume"] for e in r["trace"])
    assert "détail détaillé" in resumes and "étiquettes : spéculatif" in resumes
    assert "compatible avec ajustement" in resumes and "ampleur de la pire baisse" in resumes
    for identifiant in ("detaille", "speculatif", "compatible_avec_ajustement", "plus_grosse_action", "ecarte_esg"):
        assert identifiant not in resumes, identifiant


def test_prompt_systeme_cadre():
    texte = inspection.PROMPT_SYSTEME.read_text(encoding="utf-8")
    assert "180" in texte and "lister_instruments" in texte and "pas une recommandation" in texte
    assert "inspection" not in texte.lower()  # vocabulaire de l'interface : « analyse »


def test_trace_garde_l_ordre_des_appels_paralleles():
    scenario = [[("lire_fiche_client", {"client_id": "mateo"}), ("lire_fiche_instrument", {"ticker": "XOM"})],
                [("simuler_ordre", {"client_id": "mateo", "ticker": "XOM", "sens": "achat", "pourcentage": 8})],
                "Incompatible."]
    r = inspection.inspecter("mateo", "XOM", "achat", 8, modele=ModeleSimule(scenario, raisonnement=None))
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"]
    assert "Contrainte stricte violée : écarté ESG" in r["trace"][2]["resultat_resume"]
    assert "contraintes strictes : écarté ESG" in r["trace"][0]["resultat_resume"]


def test_limite_de_tours():
    boucle = [[("lire_fiche_instrument", {"ticker": "TSLA"})]]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(boucle))
    assert r["explication"] is None and r["erreur"]
    assert 1 <= len(r["trace"]) <= inspection.LIMITE_TOURS


def test_inspecter_ne_leve_jamais():
    from botocore.exceptions import ClientError
    e = ClientError({"Error": {"Code": "ExpiredTokenException",
                               "Message": "arn:aws:sts::123456789012:assumed-role/x expired"}}, "ConverseStream")
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule([], erreur=e))
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
    r = inspection.inspecter("robert", "TSLA", "achat", 15)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "chercher_taille_compatible"],
                       outils), outils


def _mots(texte: str) -> int:
    import re
    return len(re.findall(r"[\w’'-]*\w", texte))


@bedrock
def test_6_cas_1_substitut_et_longueur():
    r = inspection.inspecter("robert", "TSLA", "achat", 15)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert outils[:4] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre", "chercher_taille_compatible"]
    assert "lister_instruments" in outils and r["substitut"] and r["substitut"]["ticker"] != "TSLA", outils
    assert _mots(r["explication"]) <= 180
    assert "recommand" not in r["explication"].lower()


@bedrock
def test_6_cas_2_mateo_xom_ne_cherche_pas_de_taille():
    r = inspection.inspecter("mateo", "XOM", "achat", 8)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"], outils), outils
    assert "chercher_taille_compatible" not in outils
    assert "lister_instruments" not in outils and r["substitut"] is None  # chemin visiblement différent du cas 1
    assert _mots(r["explication"]) <= 180


@bedrock
def test_decouvert_debutante_ne_cherche_pas_de_taille():
    fiche = {"persona": "robert", "questionnaire": {"experience": "debutante"}}
    r = inspection.inspecter(fiche, "TSLA", "vente", 5, operation="decouvert")
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"], outils), outils
    assert "chercher_taille_compatible" not in outils
    simulation = next(e for e in r["trace"] if e["outil"] == "simuler_ordre")
    assert simulation["arguments"].get("operation") == "decouvert"
    assert simulation["resultat"]["verdict"]["code"] == "incompatible"
    assert len(r["explication"].split()) <= 200  # limite de 180 mots dans le prompt, marge pour les marqueurs **


# --- Suivi en direct des étapes ------------------------------------------------------------------

def test_suivi_des_etapes_avec_modele_simule():
    evenements = []
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_SUBSTITUT),
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
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), sur_etape=casse)
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
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_PISTES))
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
    assert "payé par la vente de 10 % de XBB.TO" in pistes[3]["description"]
    assert all(set(p) == {"famille", "libelle_famille", "description", "ordres", "verdict", "score", "direction",
                          "etape"} for p in pistes)
    assert r["substitut"]["ticker"] == "SPY"                     # le champ existant reste cohérent
    assert r["trace"][6]["resultat_resume"].startswith("Scénario : achat de 7,5 % de TSLA, achat de 7,5 % de XIU.TO.")
    json.dumps(r)


def test_pas_de_piste_pour_l_ordre_lui_meme_ni_pour_une_erreur():
    scenario = SCENARIO_ROBERT[:3] + [
        [("simuler_scenario", {"client_id": "robert", "ordres": [{"ticker": "RY.TO", "sens": "achat", "pourcentage": 15},
                                                                  {"ticker": "SPY", "sens": "achat", "pourcentage": 5}]})],
        "Texte."]
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(scenario))
    assert r["pistes"] == []
    assert inspection.inspecter("mateo", "XOM", "achat", 8, modele=ModeleSimule(
        [[("simuler_ordre", {"client_id": "mateo", "ticker": "XOM", "sens": "achat", "pourcentage": 8})], "X."]))["pistes"] == []


def test_montant_plus_petit_sans_taille_compatible():
    trace = [{"etape": 1, "outil": "simuler_ordre", "arguments": {}, "resultat": api.simuler_ordre("robert", "BTC-USD", "achat", 5)},
             {"etape": 2, "outil": "chercher_taille_compatible", "arguments": {},
              "resultat": api.chercher_taille_compatible("robert", "BTC-USD", "achat", 5)}]
    p = inspection.extraire_pistes(trace, "BTC-USD", "achat", 5)
    if trace[1]["resultat"]["taille_compatible_pct"] is None:
        assert p[0]["verdict"]["code"] == "en_tension" and p[0]["description"].startswith("Aucun montant compatible")
    else:
        assert p[0]["verdict"]["code"] == "compatible"
