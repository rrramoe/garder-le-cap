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

CHAMPS = {"explication", "trace", "modele", "duree_s", "erreur", "garde_fou", "ancrage"}
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


def test_trace_garde_l_ordre_des_appels_paralleles():
    scenario = [[("lire_fiche_client", {"client_id": "mateo"}), ("lire_fiche_instrument", {"ticker": "XOM"})],
                [("simuler_ordre", {"client_id": "mateo", "ticker": "XOM", "sens": "achat", "pourcentage": 8})],
                "Incompatible."]
    r = inspection.inspecter("mateo", "XOM", "achat", 8, modele=ModeleSimule(scenario, raisonnement=None))
    assert [e["outil"] for e in r["trace"]] == ["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"]
    assert "Contrainte stricte violée : ecarte_esg" in r["trace"][2]["resultat_resume"]


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


@bedrock
def test_6_cas_2_mateo_xom_ne_cherche_pas_de_taille():
    r = inspection.inspecter("mateo", "XOM", "achat", 8)
    _verifier_rapport(r)
    outils = [e["outil"] for e in r["trace"]]
    assert _sous_suite(["lire_fiche_client", "lire_fiche_instrument", "simuler_ordre"], outils), outils
    assert "chercher_taille_compatible" not in outils
