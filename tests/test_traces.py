"""Traces des analyses dans l'espace AWS privé (faux S3 et faux CloudWatch Logs : rien n'est écrit pour de vrai)."""
import json

import pytest

from agent import inspection, memoire, traces
from moteur import donnees
from tests.test_agent import (LECTURES_ROBERT, MANDAT, PARTAGE, SCENARIO_ROBERT, ModeleSimule)

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)


class FauxS3:
    def __init__(self, panne=False):
        self.objets, self.panne = {}, panne

    def put_object(self, Bucket, Key, Body, ContentType):
        if self.panne:
            raise RuntimeError("S3 en panne")
        self.objets[(Bucket, Key)] = json.loads(Body.decode("utf-8"))


class FauxLogs:
    def __init__(self, panne=False):
        self.lignes, self.panne = [], panne

    def create_log_group(self, **kwargs):
        raise RuntimeError("existe déjà")

    def create_log_stream(self, **kwargs):
        pass

    def put_log_events(self, logGroupName, logStreamName, logEvents):
        if self.panne:
            raise RuntimeError("Logs en panne")
        self.lignes += [(logGroupName, logStreamName, json.loads(e["message"])) for e in logEvents]


@pytest.fixture
def faux_aws(tmp_path, monkeypatch):
    monkeypatch.setenv("GLC_BUCKET", "bucket-essai")
    monkeypatch.delenv("GLC_TRACES", raising=False)
    monkeypatch.setenv("GLC_MEMOIRE_FICHIER", str(tmp_path / "analyses.json"))
    memoire.oublier()
    s3, logs = FauxS3(), FauxLogs()
    monkeypatch.setattr(traces, "CLIENTS", (s3, logs))
    monkeypatch.setattr(traces, "ATTENDRE", True)
    yield s3, logs
    memoire.oublier()


CHEF = [LECTURES_ROBERT, [("envoyer_explorateur", MANDAT)],
        [("juger_pistes", {"client_id": "robert", "decision": "suffisant"})], "**Le verdict.** En tension."]
EXPLO = [[("simuler_scenario", {"client_id": "robert", "ordres": PARTAGE, "raison": "Partage."})],
         "Pistes retenues : 1\nBilan : un partage."]


def _analyser(**options):
    return inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(CHEF), equipe=True, chef=True,
                                modele_explorateur=ModeleSimule(EXPLO), tracer=True, memoire=True, **options)


def test_une_trace_ecrite_avec_ses_champs(faux_aws):
    s3, logs = faux_aws
    r = _analyser()
    assert r["trace_aws"] and len(s3.objets) == 1
    (bucket, cle), trace = next(iter(s3.objets.items()))
    assert bucket == "bucket-essai" and cle == f"traces/{trace['heure_utc'][:10]}/{r['trace_aws']['id']}.json"
    for champ in ("identifiant", "heure_utc", "version_application", "fiche", "ordre", "modele", "reglages", "etapes",
                  "chef_de_dossier", "explorateur", "pistes", "controles", "garde_fou", "verdict_du_moteur",
                  "direction_du_moteur", "angle_determinant", "explication", "duree_s", "repli"):
        assert champ in trace, champ
    assert [(e["agent"], e["outil"]) for e in trace["etapes"]][-3:] == [
        ("principal", "envoyer_explorateur"), ("explorateur", "simuler_scenario"), ("principal", "juger_pistes")]
    assert trace["chef_de_dossier"]["jugements"][0]["decision"] == "suffisant"
    assert trace["verdict_du_moteur"] == "en_tension" and trace["angle_determinant"]["angle"]
    assert trace["etapes"][3]["reponse_du_moteur"]["verdict"]["code"] == "en_tension"   # la réponse du moteur reçue
    assert logs.lignes and logs.lignes[0][0] == "garder-le-cap" and logs.lignes[0][2]["id"] == r["trace_aws"]["id"]


def test_aucun_contenu_de_la_fiche(faux_aws):
    s3, _ = faux_aws
    _analyser()
    trace = next(iter(s3.objets.values()))
    texte = json.dumps(trace, ensure_ascii=False)
    for interdit in ('"portefeuille_pct"', '"portefeuille_avant_pct"', '"portefeuille_apres_pct"', '"questionnaire"',
                     '"Robert"', "AKIA", "aws_secret"):
        assert interdit not in texte, interdit
    assert len(trace["fiche"]["empreinte"]) == 64 and trace["fiche"]["profil_deduit"]
    lecture = next(e for e in trace["etapes"] if e["outil"] == "lire_fiche_client")
    assert set(lecture["reponse_du_moteur"]) == {"profil_deduit", "empreinte_fiche"}


def test_un_rejeu_n_ecrit_aucune_trace(faux_aws):
    s3, _ = faux_aws
    premier = _analyser()
    second = _analyser()
    assert second["memoire"]["statut"] == "deja_faite" and len(s3.objets) == 1
    assert second["trace_aws"]["id"] == premier["trace_aws"]["id"]          # l'identifiant de la trace d'origine


def test_un_client_en_panne_ne_casse_rien(faux_aws, monkeypatch):
    monkeypatch.setattr(traces, "CLIENTS", (FauxS3(panne=True), FauxLogs(panne=True)))
    r = _analyser()
    assert r["erreur"] is None and r["explication"] == "**Le verdict.** En tension." and r["trace_aws"]


def test_traces_eteintes_ou_sans_bucket(faux_aws, monkeypatch):
    s3, _ = faux_aws
    monkeypatch.setenv("GLC_TRACES", "0")
    assert _analyser()["trace_aws"] is None and not s3.objets
    monkeypatch.delenv("GLC_TRACES")
    monkeypatch.setenv("GLC_BUCKET", "")
    memoire.oublier()
    assert _analyser(relancer=True)["trace_aws"] is None and not s3.objets


def test_pas_de_trace_par_defaut_pour_un_modele_simule(faux_aws):
    s3, _ = faux_aws
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert r["trace_aws"] is None and not s3.objets
