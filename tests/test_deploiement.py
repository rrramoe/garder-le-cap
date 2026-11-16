"""Scripts de déploiement : droits minimaux, aucun secret dans l'amorçage, gel après 23 h 59."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "deploiement"))

import glc_deploiement as d  # noqa: E402


def test_politique_instance_minimale():
    p = d.politique_instance("000000000000", "bucket-essai")
    actions = {a for s in p["Statement"] for a in s["Action"]}
    assert actions == {"bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail",
                       "s3:GetObject", "s3:ListBucket"}
    assert all(r != "*" for s in p["Statement"] for r in s["Resource"])
    assert "s3:PutObject" not in json.dumps(p)


def test_amorcage_generique():
    texte = (RACINE / "deploiement" / "amorcage.sh").read_text()
    for interdit in ("AWS_ACCESS_KEY", "AWS_SECRET", "AWS_SESSION_TOKEN", "GLC_BUCKET", "GLC_GARDE_FOU"):
        assert interdit not in texte


def test_script_mise_a_jour_sans_identifiant():
    lignes = "\n".join(d.script_mise_a_jour("bucket-essai", "a" * 40))
    assert "AWS_ACCESS_KEY" not in lignes and "AWS_SECRET" not in lignes
    assert "systemctl restart glc" in lignes


def test_gel_apres_minuit_est():
    d.verifier_gel(datetime(2026, 11, 16, 4, 58, tzinfo=timezone.utc))
    with pytest.raises(SystemExit):
        d.verifier_gel(datetime(2026, 11, 16, 4, 59, tzinfo=timezone.utc))
