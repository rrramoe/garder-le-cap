"""Modèle en cinq familles : chaque nouvelle mesure recalculée ici de façon indépendante."""
import numpy as np
import pandas as pd
import pytest

from moteur import api, donnees, references

D = donnees.dossier_donnees()
pytestmark = pytest.mark.skipif(
    not all((D / f).exists() for f in ("prices_daily.csv", "corporate_actions.csv")),
    reason="fichiers des organisateurs absents de data/",
)
PROFILS = references.charger("profils")["profils"]
CLASSES = references.charger("classes")["classes"]


def _client(objectif, port, fluctuations="moderees", horizon="8_12", **q):
    return {"id": "essai", "nom": "Essai", "portefeuille_pct": port,
            "questionnaire": {"objectif": objectif, "horizon": horizon, "fluctuations": fluctuations,
                              "experience": "intermediaire", "themes": {}, **q}}


def _lin(x, cible, limite):
    return min(100.0, max(0.0, 100 - 50 * (x - cible) / (limite - cible)))


def _poids_actions(port):
    return sum(w for t, w in port.items() if t in CLASSES["actions"]["instruments"])


def test_resultat_general_cinq_questions():
    r = api.simuler_ordre("mateo", "XOM", "achat", 8)
    assert r["apres"]["familles"][:2] == ["objectif", "risque"]
    for fam in r["apres"]["familles"]:
        assert r["apres"]["notes"][fam]["question"].endswith("?")


def test_objectif_croissance_equilibree():
    r = api.simuler_ordre("mateo", "XOM", "achat", 8)
    port = r["portefeuille_apres_pct"]
    w = _poids_actions(port)
    f = PROFILS["equilibre"]["fourchettes"]["actions"]
    attendu = 100 - 50 * (w - f["cible"]) / (f["max"] - f["cible"]) if w > f["cible"] else \
        100 - 50 * (f["cible"] - w) / (f["cible"] - f["min"])
    m = r["apres"]["notes"]["objectif"]["mesures"]["actions"]
    assert m["note"] == pytest.approx(max(0, attendu))


def test_objectif_croissance_long_terme_cote_bas_seulement():
    haut = api.etat_des_lieux("amira")["notes"]["objectif"]
    assert haut["note"] == 100.0                       # 80 % d'actions, au-dessus de la cible : pas de pénalité
    port = {"ZST.TO": 10, "XBB.TO": 50, "SPY": 40}
    n = api.etat_des_lieux(_client("croissance_long_terme", port, fluctuations="elevees"))["notes"]["objectif"]
    f = PROFILS["croissance_maximale"]["fourchettes"]["actions"]
    assert n["note"] == pytest.approx(_lin(40, f["cible"], f["min"]))


def test_objectif_preserver_le_capital():
    port = {"ZST.TO": 10, "XBB.TO": 40, "XIU.TO": 25, "SPY": 25}
    c = _client("preserver_capital", port, fluctuations="faibles_moderees", horizon="3_5")
    m = api.etat_des_lieux(c)["notes"]["objectif"]["mesures"]["capital_preserve"]
    v = donnees.valeur_portefeuille(port)
    pire = float((v / v.shift(3 * 252) - 1).min())
    pente = abs(references.charger("limites_risque")["pire_annee_banque_pct"]["par_profil"]["conservateur"]) / 100
    assert m["valeur"] == pytest.approx(pire, abs=1e-6)
    assert m["note"] == pytest.approx(min(100, max(0, 50 + 50 * pire / pente)), abs=1e-4)
    court = api.etat_des_lieux({**c, "questionnaire": {**c["questionnaire"], "horizon": "moins_3"}})
    assert court["notes"]["objectif"]["mesures"]["capital_preserve"]["fenetre_annees"] == 1
    long_ = api.etat_des_lieux({**c, "questionnaire": {**c["questionnaire"], "horizon": "15_plus"}})
    assert long_["notes"]["objectif"]["mesures"]["capital_preserve"]["fenetre_ajustee"] is True


def test_objectif_revenu_regulier():
    a = pd.read_csv(D / "corporate_actions.csv", parse_dates=["ex_date"])
    p = pd.read_csv(D / "prices_daily.csv", parse_dates=["date"])

    def rdt(t):
        x = p[p.ticker == t].sort_values("date")
        fin = x.date.iloc[-1]
        div = a[(a.ticker == t) & (a.action == "dividend") & (a.ex_date > fin - pd.DateOffset(months=12))].value.sum()
        return div / x.close.iloc[-1]

    port = {"ZST.TO": 10, "XBB.TO": 50, "RY.TO": 20, "ENB.TO": 20}
    m = api.etat_des_lieux(_client("revenu_regulier", port, fluctuations="faibles"))["notes"]["objectif"]["mesures"]["revenu"]
    attendu = sum(w / 100 * rdt(t) for t, w in port.items())
    assert m["valeur"] == pytest.approx(attendu, abs=1e-3)
    assert m["limite"] < m["cible"]
    assert m["note"] == pytest.approx(_lin(m["valeur"], m["cible"], m["limite"]), abs=1e-6)
