"""Solidité du verdict (section 7.7) : deux fenêtres, même côté de 50 ou non."""
import pytest

from moteur import api, client, donnees, notation, solidite

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)



@pytest.fixture(autouse=True)
def sans_geographie(monkeypatch):
    """Ces essais portent sur une autre règle : la mesure géographique (testée dans test_familles) est mise de côté."""
    monkeypatch.setattr(notation, "mesure_geographie", lambda ex: {"note": None, "statut": "sans_objet"})

def _solidite(persona, ticker, pct):
    f = client.construire_fiche(persona)
    r = notation.simuler(f, ticker, "achat", pct)
    return r, solidite.solidite(r["portefeuille_apres_pct"], f, r["apres"])


def test_fenetres():
    defav = solidite._rendements_fenetre("defavorable")
    fav = solidite._rendements_fenetre("favorable")
    assert set(defav.index.year) == {2022}
    rend = donnees.rendements_cad()
    assert len(defav) + len(fav) == len(rend)
    # les dates d'après 2022 sont avancées de 365 jours : la série reste croissante, sans trou d'un an
    assert fav.index.is_monotonic_increasing and fav.index.is_unique
    assert fav.iloc[-1].equals(rend.iloc[-1])


def test_regle_meme_cote_de_50():
    for persona, ticker, pct in [("robert", "TSLA", 15), ("robert", "TSLA", 11.5), ("amira", "NVDA", 7)]:
        r, s = _solidite(persona, ticker, pct)
        cotes = {f["score"] >= 50 for f in s["fenetres"].values()}
        assert s["statut"] == ("solide" if len(cotes) == 1 else "fragile")
        assert s["score_principal"] == r["apres"]["score"]  # le score principal reste la période complète


def test_score_de_fenetre_est_le_minimum():
    r, s = _solidite("robert", "TSLA", 15)
    for f in s["fenetres"].values():
        autres = [r["apres"]["notes"][k]["note"] for k in ("diversification", "preferences")]
        assert f["score"] == pytest.approx(min([f["note_risque"]["note"], *autres]))


def test_robert_tsla_15_solide_et_11_5_fragile():
    assert _solidite("robert", "TSLA", 15)[1]["statut"] == "solide"   # en tension dans les deux fenêtres
    assert _solidite("robert", "TSLA", 11.5)[1]["statut"] == "fragile"  # la taille compatible dépend de la fenêtre


def test_fenetre_complete_retrouve_la_note_de_risque():
    """Contrôle des formules : sans retrait, on retrouve la note de risque du moteur."""
    f = client.construire_fiche("robert")
    port = notation.simuler(f, "TSLA", "achat", 15)["portefeuille_apres_pct"]
    v = donnees.valeur_portefeuille(port)
    assert donnees.pire_baisse(v) == pytest.approx(notation.note_risque(port, f)["mesures"]["ampleur"]["pire_baisse"])


def test_api_simuler_ordre_et_solidite():
    r = api.simuler_ordre("robert", "TSLA", "achat", 15)
    assert r["solidite"]["statut"] == "solide" and set(r["solidite"]["fenetres"]) == {"defavorable", "favorable"}
    assert any(s["id"] == "hypothese_solidite" for s in r["sources"])
    s = api.solidite("robert", "TSLA", "achat", 11.5)
    assert s["statut"] == "fragile" and s["sources"]
    assert "erreur" in api.solidite("robert", "INCONNU", "achat", 5)
