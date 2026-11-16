"""Contrat de l'API : JSON, sources, erreurs en français, aucune exception."""
import json

import pytest

from moteur import api, donnees

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)

APPELS = [
    (api.lire_fiche_client, ("robert",)),
    (api.lire_fiche_instrument, ("TSLA",)),
    (api.lister_instruments, ("actions",)),
    (api.lister_instruments, ()),
    (api.etat_des_lieux, ("mateo",)),
    (api.simuler_ordre, ("amira", "NVDA", "achat", 7)),
    (api.simuler_ordre, ("amira", "NVDA", "vente", 5)),
    (api.chercher_taille_compatible, ("robert", "TSLA", "achat", 15)),
]



def _publiee(n):
    """Note brute (limite à 50) portée sur l'échelle publiée (limite à 70), recalculée ici indépendamment du moteur."""
    return n * 70 / 50 if n < 50 else 70 + (n - 50) * 30 / 50


@pytest.mark.parametrize("fn,args", APPELS)
def test_json_et_sources(fn, args):
    r = fn(*args)
    assert "erreur" not in r, r
    assert r["sources"], "champ sources vide"
    json.dumps(r)


@pytest.mark.parametrize("fn,args,mot", [
    (api.lire_fiche_client, ("inconnu",), "inconnu"),
    (api.lire_fiche_instrument, ("XYZ",), "inconnu"),
    (api.lister_instruments, ("immobilier",), "Classe inconnue"),
    (api.simuler_ordre, ("robert", "TSLA", "achat", 20), "marge"),
    (api.simuler_ordre, ("robert", "TSLA", "vente", 1), "Vente impossible"),
    (api.simuler_ordre, ("robert", "ZST.TO", "achat", 1), "encaisse"),
    (api.simuler_ordre, ("robert", "TSLA", "achat", -2), "positif"),
    (api.simuler_ordre, ("robert", "TSLA", "garder", 2), "Sens invalide"),
    (api.lire_fiche_client, ({"persona": "robert", "questionnaire": {"horizon": "50_ans"}},), "invalide"),
    (api.lire_fiche_client, (42,), "persona"),
])
def test_erreurs(fn, args, mot):
    r = fn(*args)
    assert set(r) == {"erreur"}
    assert mot in r["erreur"]


def test_fiche_modifiee_change_les_deductions():
    r = api.lire_fiche_client({"persona": "robert", "questionnaire": {"fluctuations": "elevees"}})
    assert r["deduit"]["profil"]["valeur"] == "croissance_maximale"
    assert r["deduit"]["crypto_pct"]["valeur"]["plafond_pct"] == 6
    # une fiche renvoyée par l'API est elle-même acceptée en entrée
    assert api.lire_fiche_client(api.lire_fiche_client("mateo"))["deduit"]["profil"]["valeur"] == "equilibre"


def test_vente_dans_un_theme_recherche():
    r = api.simuler_ordre("amira", "BTC-USD", "vente", 3)
    pref = r["apres"]["notes"]["preferences"]["mesures"]["crypto"]
    assert pref["poids_vendu"] == 3
    assert pref["note"] == pytest.approx(_publiee(90))
    assert r["portefeuille_apres_pct"]["ZST.TO"] == pytest.approx(11)


def test_achat_favorable_signale():
    r = api.simuler_ordre("amira", "NVDA", "achat", 1)
    assert any(s["theme"] == "techno" for s in r["apres"]["notes"]["preferences"]["signalements"])


def test_contrainte_obligatoire_indeterminee_violee():
    fiche = {"persona": "mateo", "questionnaire": {"themes": {"ecarte_esg": "neutre", "etablie": "obligatoire"}}}
    # ESGV : thème sans objet pour un fonds -> ignoré
    assert api.simuler_ordre(fiche, "SPY", "achat", 1)["contraintes_strictes"]["violee"] is False
    # TSLA : spéculatif donc non établi -> violée
    assert api.simuler_ordre(fiche, "TSLA", "achat", 1)["verdict"]["code"] == "incompatible"


def test_exclure_indetermine_signale():
    r = api.simuler_ordre("mateo", "JPM", "achat", 2)
    d = r["contraintes_strictes"]["detail"][0]
    assert d["statut"] == "signalee"
    assert r["contraintes_strictes"]["violee"] is False


def test_prix_absents(tmp_path, monkeypatch):
    for nom in ("assets_universe.csv", "fx_usdcad_daily.csv"):
        (tmp_path / nom).write_bytes((donnees.RACINE / "data" / nom).read_bytes())
    monkeypatch.setenv("GLC_DATA_DIR", str(tmp_path))
    r = api.etat_des_lieux("robert")
    assert set(r) == {"erreur"}
    assert "build_dataset.py" in r["erreur"]
