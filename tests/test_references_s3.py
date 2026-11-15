"""Fichiers de référence lus dans Amazon S3 (bucket privé) ou dans le dossier local.

Hors ligne, S3 est remplacé par un client simulé. La lecture réelle est sautée sans identifiants AWS
(ou avec GLC_SANS_AWS=1) et sans bucket configuré dans `glc.env`.
"""
import importlib.util
import io
import json
import os
from pathlib import Path

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from agent import identifiants
from moteur import api, configuration, references

RACINE = Path(__file__).resolve().parents[1]


class S3Simule:
    def __init__(self, erreur=None, modifie=None):
        self.erreur, self.modifie, self.cles = erreur, modifie or {}, []

    def get_object(self, Bucket, Key):
        self.cles.append((Bucket, Key))
        if self.erreur:
            raise self.erreur
        nom = Path(Key).stem
        corps = self.modifie.get(nom) or (references.DOSSIER_REFERENCE / f"{nom}.json").read_bytes()
        return {"Body": io.BytesIO(corps)}


@pytest.fixture
def propre(tmp_path, monkeypatch):
    monkeypatch.setenv("GLC_CONFIG", str(tmp_path / "absent.env"))
    for v in configuration.VARIABLES:
        monkeypatch.delenv(v, raising=False)
    references.reinitialiser()
    yield monkeypatch
    references.reinitialiser()


def test_sans_bucket_lecture_locale(propre):
    assert references.charger("classes")["encaisse"] == "ZST.TO"
    o = references.origine()
    assert o["lieu"] == "local" and "non configuré" in o["message"]


def test_avec_bucket_lecture_s3(propre):
    s3 = S3Simule()
    propre.setenv("GLC_BUCKET", "bucket-essai")
    propre.setattr(references, "_client_s3", lambda: s3)
    assert references.charger("classes")["encaisse"] == "ZST.TO"
    assert s3.cles == [("bucket-essai", "reference/classes.json")]
    references.charger("classes")
    assert len(s3.cles) == 1  # lu une seule fois
    o = references.origine()
    assert o["lieu"] == "s3" and "Amazon S3" in o["message"] and o["fichiers"]["classes"]["identique_au_local"]


@pytest.mark.parametrize("erreur,raison", [
    (NoCredentialsError(), "identifiants AWS absents"),
    (ClientError({"Error": {"Code": "ExpiredToken"}}, "GetObject"), "identifiants AWS expirés"),
    (ClientError({"Error": {"Code": "NoSuchBucket"}}, "GetObject"), "bucket introuvable"),
])
def test_s3_en_panne_repli_local(propre, erreur, raison):
    propre.setenv("GLC_BUCKET", "bucket-essai")
    propre.setattr(references, "_client_s3", lambda: S3Simule(erreur))
    assert references.charger("classes")["encaisse"] == "ZST.TO"
    o = references.origine()
    assert o["lieu"] == "local" and raison in o["message"] and "n'a pas répondu" in o["message"]


def test_copie_s3_differente_signalee(propre):
    propre.setenv("GLC_BUCKET", "bucket-essai")
    autre = json.dumps({"encaisse": "ZST.TO", "classes": {}}).encode()
    propre.setattr(references, "_client_s3", lambda: S3Simule(modifie={"classes": autre}))
    references.charger("classes")
    assert "différente du dossier local pour classes" in references.origine()["message"]


def test_api_origine_references(propre):
    references.charger("profils")
    r = api.origine_references()
    assert r["lieu"] == "local" and r["message"] and r["sources"]


def _script():
    spec = importlib.util.spec_from_file_location("creer_bucket", RACINE / "scripts" / "creer_bucket.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_bucket_prive():
    m = _script()
    assert all(m.BLOCAGE_PUBLIC.values()) and len(m.BLOCAGE_PUBLIC) == 4
    politique = json.loads(m.politique_tls("b"))
    assert politique["Statement"][0]["Effect"] == "Deny"
    assert politique["Statement"][0]["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}


# --- Lecture réelle -----------------------------------------------------------------------------

def _s3_reel() -> bool:
    return (os.environ.get("GLC_SANS_AWS") != "1" and identifiants.identifiants_disponibles()
            and configuration.valeur("GLC_BUCKET") is not None)


@pytest.mark.skipif(not _s3_reel(), reason="identifiants AWS ou bucket absents : lecture réelle sautée")
def test_reel_lecture_s3_et_bucket_prive():
    references.reinitialiser()
    try:
        assert references.charger("profils") == references._lire_local("profils")
        assert references.origine()["fichiers"]["profils"]["lieu"] == "s3"
    finally:
        references.reinitialiser()
    s3 = references._client_s3()
    assert _script().verifier(s3, configuration.valeur("GLC_BUCKET")) == []
