"""Tests de `api.decrire_apport` : chaque partie, avec un calcul indépendant en pandas."""

import pandas as pd
import pytest

from moteur import api, donnees, instruments, references


def _rendements_independants() -> pd.DataFrame:
    # Recalcul indépendant : rendements simples des prix en CAD, jours sans cotation à 0.
    return donnees.prix_cad().pct_change().iloc[1:].fillna(0.0)


def _rendement_portefeuille(port: dict) -> pd.Series:
    rend = _rendements_independants()
    total = sum(port.values())
    return sum(rend[t] * (w / total) for t, w in port.items())


def _portefeuille(persona: str) -> dict:
    return {t: float(w) for t, w in references.charger("personas")["personas"][persona]["portefeuille_pct"].items()}


@pytest.fixture(scope="module")
def robert_tsla():
    return api.decrire_apport("robert", "TSLA", 15)


def test_correlation_avec_le_portefeuille(robert_tsla):
    rend = _rendements_independants()
    attendu = rend["TSLA"].corr(_rendement_portefeuille(_portefeuille("robert")))
    c = robert_tsla["correlation_portefeuille"]
    assert c["valeur"] == pytest.approx(attendu, abs=1e-5)
    assert c["deja_detenu_pct"] == 0
    assert c["periode"] == {"debut": "2021-11-12", "fin": "2026-11-12", "devise": "CAD"}


def test_trois_positions_les_plus_proches(robert_tsla):
    rend = _rendements_independants()
    port = _portefeuille("robert")
    corr = {t: rend[t].corr(rend["TSLA"]) for t in port}
    attendu = sorted(corr, key=corr.get, reverse=True)[:3]
    proches = robert_tsla["positions_proches"]
    assert [p["ticker"] for p in proches] == attendu
    for p in proches:
        assert p["correlation"] == pytest.approx(corr[p["ticker"]], abs=1e-5)
        assert p["poids_pct"] == port[p["ticker"]]


def test_exposition_actuelle_classe_secteur_etiquettes(robert_tsla):
    port = _portefeuille("robert")
    actions = sum(w for t, w in port.items() if instruments.fiche(t)["classe_politique"] == "actions")
    e = robert_tsla["exposition_actuelle"]
    assert e["classe"]["classe"] == "actions" and e["classe"]["poids_pct"] == pytest.approx(actions)
    assert (e["classe"]["min_pct"], e["classe"]["max_pct"]) == (20, 45)
    assert e["secteur"]["secteur"] == "Consumer Discretionary" and e["secteur"]["poids_pct"] == 0
    assert e["secteur"]["plafond_pct"] == 40
    assert e["etiquettes"]["speculatif"]["poids_pct"] == 0
    assert e["etiquettes"]["speculatif"]["reponse_client"] == "eviter"


def test_exposition_aux_etiquettes_deja_detenues():
    r = api.decrire_apport("amira", "NVDA")
    port = _portefeuille("amira")
    for etiquette, bloc in r["exposition_actuelle"]["etiquettes"].items():
        attendu = sum(w for t, w in port.items() if instruments.fiche(t)["etiquettes"].get(etiquette, {}).get("valeur") is True)
        assert bloc["poids_pct"] == pytest.approx(attendu), etiquette
    assert r["exposition_actuelle"]["etiquettes"]["speculatif"]["poids_pct"] > 0  # NVDA déjà détenue
    assert r["apres_ordre"] is None  # sans pourcentage, pas de bloc « après »


def test_part_du_portefeuille_et_du_risque_apres_l_ordre(robert_tsla):
    sim = api.simuler_ordre("robert", "TSLA", "achat", 15)["contribution_risque_apres"]
    a = robert_tsla["apres_ordre"]
    assert a["poids_pct"] == pytest.approx(15.0)
    assert a["part_du_risque_pct"] == pytest.approx(sim["part_du_risque_pct"], abs=1e-6)
    # Recalcul indépendant : w x cov(r_i, r_p) / var(r_p) sur le portefeuille après l'achat.
    port = _portefeuille("robert")
    port["ZST.TO"] -= 15
    port["TSLA"] = 15
    rend, rp = _rendements_independants(), _rendement_portefeuille(port)
    attendu = 0.15 * rend["TSLA"].cov(rp) / rp.var() * 100
    assert a["part_du_risque_pct"] == pytest.approx(attendu, abs=1e-4)


def test_candidats_de_la_meme_classe_classes_par_proximite(robert_tsla):
    rend = _rendements_independants()
    classe = [t for t, f in instruments.toutes().items() if f["classe_politique"] == "actions" and t != "TSLA"]
    cand = robert_tsla["candidats"]
    assert sorted(c["symbole"] for c in cand) == sorted(classe)
    correls = [c["correlation_avec_instrument"] for c in cand]
    assert correls == sorted(correls, reverse=True)
    qqq = next(c for c in cand if c["symbole"] == "QQQ")
    assert qqq["correlation_avec_instrument"] == pytest.approx(rend["QQQ"].corr(rend["TSLA"]), abs=1e-5)
    stats = instruments.fiche("QQQ")["statistiques_cad"]
    assert qqq["volatilite_annualisee"] == pytest.approx(stats["volatilite_annualisee"], abs=1e-6)
    assert qqq["pire_baisse"] == pytest.approx(stats["pire_baisse"], abs=1e-6)
    assert set(qqq["etiquettes"]) == set(instruments.fiche("QQQ")["etiquettes"])


def test_faits_seulement_avec_sources_et_periode(robert_tsla):
    assert not {"score", "verdict", "notes", "direction"} & set(robert_tsla)
    ids = {s["id"] for s in robert_tsla["sources"]}
    assert {"donnees_marche", "hypothese_conventions_calcul", "hypothese_etiquettes"} <= ids
    assert robert_tsla["periode"]["devise"] == "CAD" and robert_tsla["frequence"] == "quotidienne"


def test_erreurs_au_format_habituel():
    assert set(api.decrire_apport("robert", "ZZZ")) == {"erreur"}
    assert set(api.decrire_apport("inconnu", "TSLA")) == {"erreur"}
    assert set(api.decrire_apport("robert", "TSLA", "beaucoup")) == {"erreur"}
    r = api.decrire_apport("amira", "NVDA", 90)  # plus que l'encaisse : le reste du portrait reste valable
    assert "erreur" in r["apres_ordre"] and r["correlation_portefeuille"]["valeur"] is not None


def test_outil_de_l_agent_lie_au_client():
    from agent.outils import NOM_OUTIL_APPORT, creer_outil_decrire_apport
    outil = creer_outil_decrire_apport("mateo")
    assert outil.tool_name == NOM_OUTIL_APPORT == "decrire_apport"
    r = outil(client_id="mateo", ticker="XOM", pourcentage=8)
    assert r["apres_ordre"]["poids_pct"] == pytest.approx(8.0)
    assert "erreur" in outil(client_id="robert", ticker="XOM")
