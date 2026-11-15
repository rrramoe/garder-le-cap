"""Achat sur marge, vente à découvert, levier et contrôle de l'expérience."""
import json
from pathlib import Path

import pytest

from moteur import api, donnees, notation, references

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)

EMPREINTE = json.loads((Path(__file__).parent / "empreinte_comptant.json").read_text(encoding="utf-8"))
MARGE = ("NVDA", "achat", 20, "marge")          # Amira a 8 % d'encaisse : 12 % empruntés
DECOUVERT = ("TSLA", "vente", 5, "decouvert")   # aucun TSLA détenu : 5 % à découvert
IDS = {"marge": "achat_sur_marge", "decouvert": "vente_a_decouvert"}


def _client(experience, persona="amira"):
    return {"persona": persona, "questionnaire": {"experience": experience}}


def _notes(ev):
    return {"score": ev["score"], "dimension_min": ev["dimension_min"], "mesure_min": ev["mesure_min"],
            "mesures": {d: {m: v["note"] for m, v in ev["notes"][d]["mesures"].items()} for d in ev["notes"]}}


# --- Les appels par défaut sont inchangés -------------------------------------------------------

@pytest.mark.parametrize("cas", sorted(EMPREINTE["cas"]))
def test_defaut_identique_a_main(cas):
    client, ticker, sens, pct = cas.split("|")
    attendu = EMPREINTE["cas"][cas]
    r = api.simuler_ordre(client, ticker, sens, float(pct))
    assert r["portefeuille_apres_pct"] == attendu["portefeuille_apres_pct"]
    assert r["verdict"]["code"] == attendu["verdict"]
    assert r["direction"]["cas"] == attendu["direction"]
    assert r["contraintes_strictes"]["themes_violes"] == attendu["themes_violes"]
    assert _notes(r["avant"]) == attendu["avant"]
    assert _notes(r["apres"]) == attendu["apres"]
    assert r["contribution_risque_apres"] == attendu["contribution_risque_apres"]
    t = api.chercher_taille_compatible(client, ticker, sens, float(pct))
    assert t["lancee"] == attendu["taille"]["lancee"]
    assert t["taille_compatible_pct"] == attendu["taille"]["taille_compatible_pct"]
    assert t["courbe"] == attendu["taille"]["courbe"]
    assert "operation" not in t


def test_defaut_egal_a_comptant_explicite():
    a = api.simuler_ordre("robert", "TSLA", "achat", 15)
    b = api.simuler_ordre("robert", "TSLA", "achat", 15, "comptant")
    assert a == b
    assert a["ordre"]["operation"] == "comptant"
    assert a["operation"]["levier_avant"] == a["operation"]["levier_apres"] == 1.0
    assert a["operation"]["controle_experience"]["effet"] == "aucun"
    assert not any(d.get("controle") for d in a["contraintes_strictes"]["detail"])
    assert api.chercher_taille_compatible("robert", "TSLA", "achat", 15) == \
        api.chercher_taille_compatible("robert", "TSLA", "achat", 15, "comptant")


def test_comptant_refuse_toujours_l_achat_trop_gros_et_la_vente_non_detenue():
    assert "marge" in api.simuler_ordre("amira", "NVDA", "achat", 20)["erreur"]
    assert "Vente impossible" in api.simuler_ordre("amira", "TSLA", "vente", 5)["erreur"]


# --- Mécanique de l'ordre et levier -------------------------------------------------------------

def test_marge_encaisse_negative_et_levier():
    r = api.simuler_ordre(_client("avancee"), *MARGE)
    port = r["portefeuille_apres_pct"]
    assert port["ZST.TO"] == pytest.approx(-12.0)
    assert port["NVDA"] == pytest.approx(30.0)
    assert sum(port.values()) == pytest.approx(100.0)
    op = r["operation"]
    assert op["code"] == "marge"
    assert op["levier_apres"] == pytest.approx(1.12)
    assert op["exposition_empruntee_apres_pct"] == pytest.approx(12.0)
    # L'emprunt n'est pas une position dans le fonds de liquidités.
    assert r["apres"]["notes"]["diversification"]["mesures"]["plus_gros_fonds"]["ticker"] != "ZST.TO"


def test_decouvert_poids_negatif_produit_a_l_encaisse_et_valeur_absolue():
    r = api.simuler_ordre(_client("avancee", "robert"), *DECOUVERT)
    port = r["portefeuille_apres_pct"]
    assert port["TSLA"] == pytest.approx(-5.0)
    assert port["ZST.TO"] == pytest.approx(20.0)
    assert r["operation"]["levier_apres"] == pytest.approx(1.10)
    r10 = api.simuler_ordre(_client("avancee", "robert"), "TSLA", "vente", 10, "decouvert")
    action = r10["apres"]["notes"]["diversification"]["mesures"]["plus_grosse_action"]
    assert (action["ticker"], action["poids"]) == ("TSLA", pytest.approx(10.0))
    # Robert évite le spéculatif : TSLA à découvert compte par sa valeur absolue.
    spec = r10["apres"]["notes"]["preferences"]["mesures"]["speculatif"]
    assert spec["instruments"]["TSLA"] == pytest.approx(10.0)


def test_hypotheses_et_limites_dans_le_resultat():
    for op in (MARGE, DECOUVERT):
        r = api.simuler_ordre(_client("avancee"), *op)
        ids = {s["id"] for s in r["sources"]}
        attendu = "hypothese_marge" if op[3] == "marge" else "hypothese_decouvert"
        assert {attendu, "hypothese_levier", "hypothese_experience_operations"} <= ids
        assert all(s["nature"] == "hypothese" for s in r["sources"] if s["id"] in (attendu, "hypothese_levier"))
        assert "appel de marge" in r["operation"]["limites"][0] or "appels de marge" in r["operation"]["limites"][0]
    assert "plafond" in api.simuler_ordre(_client("avancee"), *DECOUVERT)["operation"]["limites"][0]
    assert "coût de l'emprunt" in api.simuler_ordre(_client("avancee"), *MARGE)["operation"]["limites"][0]


@pytest.mark.parametrize("args,mot", [
    (("robert", "TSLA", "vente", 5, "marge"), "sens doit être « achat »"),
    (("robert", "TSLA", "achat", 5, "decouvert"), "sens doit être « vente »"),
    (("robert", "TSLA", "achat", 5, "options"), "Opération invalide"),
    (("robert", "ZST.TO", "vente", 5, "decouvert"), "encaisse"),
    (("robert", "TSLA", "vente", -5, "decouvert"), "strictement positif"),
])
def test_erreurs_des_operations(args, mot):
    for fn in (api.simuler_ordre, api.chercher_taille_compatible):
        r = fn(*args)
        assert set(r) == {"erreur"} and mot in r["erreur"], r


# --- Contrôle de l'expérience : trois niveaux pour chaque opération -----------------------------

@pytest.mark.parametrize("ordre", [MARGE, DECOUVERT], ids=["marge", "decouvert"])
def test_debutante_exclut_et_ne_cherche_pas_de_taille(ordre):
    r = api.simuler_ordre(_client("debutante"), *ordre)
    assert r["verdict"]["code"] == "incompatible"
    assert IDS[ordre[3]] in r["contraintes_strictes"]["themes_violes"]
    assert r["operation"]["controle_experience"]["effet"] == "contrainte_stricte"
    t = api.chercher_taille_compatible(_client("debutante"), *ordre)
    assert t["lancee"] is False and t["taille_compatible_pct"] is None and t["courbe"] == []


@pytest.mark.parametrize("ordre,e", [(MARGE, 12.0), (DECOUVERT, 5.0)], ids=["marge", "decouvert"])
def test_intermediaire_preference_souple(ordre, e):
    r = api.simuler_ordre(_client("intermediaire"), *ordre)
    assert not r["contraintes_strictes"]["violee"]
    m = r["apres"]["notes"]["preferences"]["mesures"][IDS[ordre[3]]]
    assert m["poids_expose"] == pytest.approx(e)
    assert m["note"] == pytest.approx(max(0.0, 100 - 50 * e / 15))
    assert r["operation"]["controle_experience"]["effet"] == "preference_souple"
    assert r["operation"]["controle_experience"]["note"] == pytest.approx(m["note"])
    assert IDS[ordre[3]] not in r["avant"]["notes"]["preferences"]["mesures"]
    t = api.chercher_taille_compatible(_client("intermediaire"), *ordre)
    assert t["lancee"] is True and all("levier" in p for p in t["courbe"])


@pytest.mark.parametrize("ordre", [MARGE, DECOUVERT], ids=["marge", "decouvert"])
def test_avancee_neutre_sans_effet(ordre):
    r = api.simuler_ordre(_client("avancee"), *ordre)
    assert not r["contraintes_strictes"]["violee"]
    assert IDS[ordre[3]] not in r["apres"]["notes"]["preferences"]["mesures"]
    assert r["operation"]["controle_experience"]["effet"] == "aucun"
    # Mêmes notes qu'un client intermédiaire, sans la mesure d'expérience.
    i = api.simuler_ordre(_client("intermediaire"), *ordre)
    assert r["apres"]["notes"]["risque"] == i["apres"]["notes"]["risque"]
    assert r["apres"]["notes"]["diversification"] == i["apres"]["notes"]["diversification"]


def test_intermediaire_note_exactement_au_repere():
    # Mateo (10 % d'encaisse) achète 25 % de XIU.TO sur marge : 15 % empruntés, note 50.
    r = api.simuler_ordre("mateo", "XIU.TO", "achat", 25, "marge")
    assert r["apres"]["notes"]["preferences"]["mesures"]["achat_sur_marge"]["note"] == pytest.approx(50.0)


# --- Le tableau se change dans reference/, sans toucher au code ---------------------------------

def _table_modifiee(monkeypatch, niveau_debutante):
    vrai = references.charger

    def charger(nom):
        d = vrai(nom)
        if nom != "operations_experience":
            return d
        d = json.loads(json.dumps(d))
        for op in d["operations"].values():
            op["niveau_par_experience"]["debutante"] = niveau_debutante
        return d
    monkeypatch.setattr(references, "charger", charger)


def test_niveau_change_dans_le_fichier(monkeypatch):
    _table_modifiee(monkeypatch, "neutre")
    r = api.simuler_ordre(_client("debutante"), *DECOUVERT)
    assert not r["contraintes_strictes"]["violee"]
    assert r["operation"]["controle_experience"]["effet"] == "aucun"


def test_niveau_invalide_dans_le_fichier(monkeypatch):
    _table_modifiee(monkeypatch, "obligatoire")
    r = api.simuler_ordre(_client("debutante"), *DECOUVERT)
    assert set(r) == {"erreur"} and "operations_experience.json" in r["erreur"]


def test_fichier_marque_hypothese():
    ref = references.charger("operations_experience")
    assert references.sources(ref["source"])[0]["nature"] == "hypothese"
    assert set(ref["operations"]) == set(notation.OPERATIONS) - {"comptant"}
