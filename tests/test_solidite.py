"""Solidité du verdict (section 7.7) : deux fenêtres, même côté de 50 ou non."""
import pytest

from moteur import api, client, donnees, notation, solidite

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)



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
    for persona, ticker, pct in [("robert", "TSLA", 15), ("robert", "TSLA", 9), ("amira", "NVDA", 7)]:
        r, s = _solidite(persona, ticker, pct)
        cotes = {f["score"] >= 70 for f in s["fenetres"].values()}
        assert s["statut"] == ("solide" if len(cotes) == 1 else "fragile")
        assert s["score_principal"] == r["apres"]["score"]  # le score principal reste la période complète


def test_score_de_fenetre_est_le_minimum():
    r, s = _solidite("robert", "TSLA", 15)
    for f in s["fenetres"].values():
        notes = [n["note"] for k, n in r["apres"]["notes"].items() if k not in ("risque", "objectif")]
        notes += [f["note_risque"]["note"], (f["note_objectif"] or r["apres"]["notes"]["objectif"])["note"]]
        assert f["score"] == pytest.approx(min(n for n in notes if n is not None))


def test_fenetres_recalculent_toutes_les_mesures_de_l_historique():
    """Fluctuations et pire année recalculées sur la fenêtre, mêmes formules et limites (recalcul indépendant)."""
    import numpy as np
    r, s = _solidite("robert", "TSLA", 7)
    port = r["portefeuille_apres_pct"]
    for nom, f in s["fenetres"].items():
        m = f["note_risque"]["mesures"]
        assert set(m) == {"ampleur", "duree", "fluctuations", "pire_annee"}
        v = solidite.valeur_fenetre(port, nom).to_numpy()
        if len(v) > 252:
            pire = float(np.min(v[252:] / v[:-252] - 1))
            assert m["pire_annee"]["valeur"] == pytest.approx(pire)
            lim = m["pire_annee"]["limite"]
            assert m["pire_annee"]["note"] == pytest.approx(notation.convertir(min(100, max(0, 100 - 50 * pire / lim))))
        else:
            assert m["pire_annee"]["note"] is None and m["pire_annee"]["raison"] == solidite.TROP_COURTE
        if m["fluctuations"]["note"] is None:
            assert "fluctuations" in f["mesures_indeterminees"]


def test_montant_compatible_de_robert_juge_sur_la_mesure_qui_decide():
    r, s = _solidite("robert", "TSLA", 7)
    assert r["apres"]["mesure_min"] == "pire_annee" and r["verdict"]["code"] == "compatible"
    defav = s["fenetres"]["defavorable"]
    assert defav["dimension_min"] == "risque" and defav["note_risque"]["mesure_min"] == "pire_annee"
    assert s["statut"] == "solide"


def test_objectif_recalcule_par_fenetre_et_verdict_principal_inchange():
    r, s = _solidite("robert", "TSLA", 15)          # Robert : préserver son capital
    avant = r["apres"]["score"], r["verdict"]["code"]
    defav = s["fenetres"]["defavorable"]
    assert defav["note_objectif"] is not None
    assert "capital_preserve" in defav["mesures_indeterminees"]   # 2022 seule : trop courte pour 3 ans
    assert (r["apres"]["score"], r["verdict"]["code"]) == avant and s["score_principal"] == r["apres"]["score"]
    assert _solidite("mateo", "XOM", 8)[1]["fenetres"]["favorable"]["note_objectif"] is None


def test_robert_tsla_15_solide_et_9_fragile():
    assert _solidite("robert", "TSLA", 15)[1]["statut"] == "solide"   # en tension dans les deux fenêtres
    assert _solidite("robert", "TSLA", 9)[1]["statut"] == "fragile"  # la taille compatible dépend de la fenêtre


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
    s = api.solidite("robert", "TSLA", "achat", 9)
    assert s["statut"] == "fragile" and s["sources"]
    assert "erreur" in api.solidite("robert", "INCONNU", "achat", 5)
