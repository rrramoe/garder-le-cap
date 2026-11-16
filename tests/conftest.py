"""Essais hermétiques : ni la mémoire des analyses de la machine, ni une trace vers AWS, sauf demande explicite."""
import pytest


@pytest.fixture(autouse=True)
def memoire_et_traces_isolees(tmp_path, monkeypatch):
    # La mémoire des analyses lit un fichier temporaire, vide, jamais `.cache/analyses.json` du développeur.
    monkeypatch.setenv("GLC_MEMOIRE_FICHIER", str(tmp_path / "analyses.json"))
    # Aucune trace ni ligne de journal vers AWS : un essai qui en veut les rallume lui-même (tests/test_traces.py).
    monkeypatch.setenv("GLC_TRACES", "0")
    from agent import memoire
    memoire.oublier()
    yield
    memoire.oublier()
