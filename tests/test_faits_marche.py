"""Faits de marché de la fiche du titre : chaque famille recalculée ici de façon indépendante."""
import json

import numpy as np
import pandas as pd
import pytest

from moteur import api, donnees, faits_marche, instruments

D = donnees.dossier_donnees()
pytestmark = pytest.mark.skipif(
    not all((D / f).exists() for f in ("prices_daily.csv", "corporate_actions.csv", "macro_rates.csv")),
    reason="fichiers des organisateurs absents de data/ (prices_daily, corporate_actions, macro_rates)",
)


def _prix_cad(ticker):
    """Prix ajusté en CAD, recalculé à la main : calendrier XIU.TO ∪ SPY, report en avant, change du jour."""
    p = pd.read_csv(D / "prices_daily.csv", parse_dates=["date"])
    fx = pd.read_csv(D / "fx_usdcad_daily.csv", parse_dates=["date"]).set_index("date")["usdcad"]
    cal = pd.DatetimeIndex(sorted(p.loc[p.ticker.isin(["XIU.TO", "SPY"]), "date"].unique()))
    s = p[p.ticker == ticker].set_index("date")["adj_close"]
    s = s.reindex(s.index.union(cal)).ffill().reindex(cal)
    if p.loc[p.ticker == ticker, "currency"].iloc[0] == "USD":
        s = s * fx.reindex(fx.index.union(cal)).ffill().reindex(cal)
    return s.dropna()


def _faits(t):
    return instruments.fiche(t)["faits_marche"]


@pytest.mark.parametrize("t", ["NVDA", "RY.TO", "XBB.TO", "BTC-USD"])
def test_performance(t):
    s, f = _prix_cad(t), _faits(t)["performance"]
    assert f["rendement_total"] == pytest.approx(s.iloc[-1] / s.iloc[0] - 1, abs=1e-6)
    fin_2022, fin_2021 = s[s.index.year == 2022].iloc[-1], s[s.index.year == 2021].iloc[-1]
    assert f["par_annee"]["2022"] == pytest.approx(fin_2022 / fin_2021 - 1, abs=1e-6)
    assert f["ecart_au_plus_haut"] == pytest.approx(s.iloc[-1] / s.max() - 1, abs=1e-6)
    assert set(f["annees_partielles"]) == {2021, 2026}
    completes = {a: r for a, r in f["par_annee"].items() if int(a) not in f["annees_partielles"]}
    assert f["pire_annee"]["rendement"] == min(completes.values())


@pytest.mark.parametrize("t", ["TSLA", "XIU.TO"])
def test_risque(t):
    s, f = _prix_cad(t), _faits(t)["risque"]
    r = s.pct_change().dropna().to_numpy()
    neg = [x * x if x < 0 else 0.0 for x in r]
    assert f["volatilite_baissiere"] == pytest.approx((sum(neg) / len(neg)) ** 0.5 * 252 ** 0.5, abs=1e-6)
    assert f["pire_jour"]["rendement"] == pytest.approx(r.min(), abs=1e-6)
    # baisses de plus de 20 % : compte à la main sur le prix
    n, dedans, sommet = 0, False, -np.inf
    for v in s.to_numpy():
        if v >= sommet:
            sommet, dedans = v, False
        elif v / sommet - 1 < -0.2 and not dedans:
            n, dedans = n + 1, True
    assert f["baisses_de_plus_de_20_pct"] == n


def test_marches_et_change():
    a, m = _prix_cad("AAPL").pct_change().dropna(), _prix_cad("SPY").pct_change().dropna()
    d = pd.concat([a, m], axis=1).dropna().to_numpy()
    beta = np.cov(d[:, 0], d[:, 1])[0, 1] / np.var(d[:, 1], ddof=1)
    f = _faits("AAPL")["marches"]
    assert f["actions_etats_unis"]["beta"] == pytest.approx(beta, abs=1e-4)
    assert f["actions_etats_unis"]["correlation"] == pytest.approx(np.corrcoef(d[:, 0], d[:, 1])[0, 1], abs=1e-4)
    assert _faits("XBB.TO")["marches"]["obligations_canada"]["correlation"] == pytest.approx(1.0)
    assert _faits("RY.TO")["marches"]["part_volatilite_due_au_change"] == "sans_objet"
    assert isinstance(f["part_volatilite_due_au_change"], float)


def test_revenu():
    a = pd.read_csv(D / "corporate_actions.csv", parse_dates=["ex_date"])
    p = pd.read_csv(D / "prices_daily.csv", parse_dates=["date"])
    ry = p[p.ticker == "RY.TO"].sort_values("date")
    fin, dernier = ry.date.iloc[-1], ry.close.iloc[-1]
    div = a[(a.ticker == "RY.TO") & (a.action == "dividend") & (a.ex_date > fin - pd.DateOffset(months=12))].value.sum()
    f = _faits("RY.TO")["revenu"]
    assert f["dividendes_12_mois"] == pytest.approx(div, abs=1e-4)
    assert f["rendement_dividende"] == pytest.approx(div / dernier, abs=1e-4)
    assert _faits("BTC-USD")["revenu"]["annees_avec_dividende"] == 0
    assert _faits("BTC-USD")["revenu"]["dividende_en_hausse"] == "indetermine"
    splits = a[(a.ticker == "NVDA") & (a.action == "split")]
    assert len(_faits("NVDA")["revenu"]["fractionnements"]) == len(splits)


def test_liquidite_et_jours_de_volume():
    p = pd.read_csv(D / "prices_daily.csv", parse_dates=["date"])
    x = p[p.ticker == "RY.TO"].sort_values("date").tail(63)
    moyenne = float((x.close * x.volume).mean())
    f = _faits("RY.TO")["liquidite"]
    assert f["valeur_echangee_moyenne_par_jour_cad"] == pytest.approx(moyenne, rel=1e-6)
    r = api.lire_fiche_instrument("RY.TO", 1_000_000)
    assert r["faits_marche"]["liquidite"]["jours_de_volume_ordre"] == pytest.approx(1_000_000 / moyenne, abs=1e-6)
    assert "jours_de_volume_ordre" not in api.lire_fiche_instrument("RY.TO")["faits_marche"]["liquidite"]


def test_taux():
    m = pd.read_csv(D / "macro_rates.csv", parse_dates=["date"])
    t = m[m.series_id == "BD.CDN.10YR.DQ.YLD"].set_index("date")["value"].sort_index()
    s = _prix_cad("XBB.TO")
    h = pd.concat([s.resample("W-FRI").last().pct_change(), t.resample("W-FRI").last().diff()], axis=1).dropna()
    assert _faits("XBB.TO")["taux"]["correlation_avec_taux_10_ans"] == pytest.approx(
        np.corrcoef(h.iloc[:, 0], h.iloc[:, 1])[0, 1], abs=1e-4)
    assert _faits("AAPL")["taux"]["serie"] == "DGS10"


def test_identite_et_sources():
    u = pd.read_csv(D / "assets_universe.csv").set_index("ticker")
    for t, ligne in u.iterrows():
        f = instruments.fiche(t)
        assert (f["identifiant_univers"], f["nom"], f["classe_actif"], f["marche"], f["devise"], f["secteur"]) == \
            (ligne.asset_id, ligne["name"], ligne.asset_class, ligne.market, ligne.currency, ligne.sector)
    r = api.lire_fiche_instrument("XOM")
    assert {"donnees_dividendes", "donnees_taux", "hypothese_faits_marche"} <= {s["id"] for s in r["sources"]}
    json.dumps(r)


def test_candidats_portent_type_et_dividende():
    r = api.decrire_apport("mateo", "XOM", 5)
    c = {x["symbole"]: x for x in r["candidats"]}
    assert c["CNQ.TO"]["type"] == "action" and c["SPY"]["type"] == "fonds"
    assert c["CNQ.TO"]["rendement_dividende"] == _faits("CNQ.TO")["revenu"]["rendement_dividende"]


# ---------------------------------------------------------------- trois thèmes de plus (données)
# Un client neuf, sans persona : une fiche et un portefeuille suffisent.

CLIENT_NEUF = {"id": "nouveau", "nom": "Client neuf",
               "questionnaire": {"objectif": "croissance_equilibree", "horizon": "8_12", "fluctuations": "moderees",
                                 "experience": "intermediaire", "themes": {}},
               "portefeuille_pct": {"ZST.TO": 20, "XBB.TO": 35, "XIU.TO": 25, "SPY": 20}}


def _client(**themes):
    c = json.loads(json.dumps(CLIENT_NEUF))
    c["questionnaire"]["themes"] = themes
    return c


def test_etiquettes_des_nouveaux_themes_suivent_les_donnees():
    a = pd.read_csv(D / "corporate_actions.csv", parse_dates=["ex_date"])
    u = pd.read_csv(D / "assets_universe.csv").set_index("ticker")
    fin = pd.read_csv(D / "prices_daily.csv", parse_dates=["date"]).groupby("ticker").date.max()
    for t, ligne in u.iterrows():
        e = instruments.fiche(t)["etiquettes"]
        verse = bool(((a.ticker == t) & (a.action == "dividend") & (a.value > 0)
                      & (a.ex_date > fin[t] - pd.DateOffset(months=12))).any())
        assert e["dividende"]["valeur"] is verse, t
        assert e["devise_etrangere"]["valeur"] is (ligne.currency != "CAD"), t
        assert e["action_individuelle"]["valeur"] is (ligne.asset_class == "equity"), t


def test_themes_neutres_par_defaut_pour_un_client_neuf():
    r = api.lire_fiche_client(CLIENT_NEUF)
    assert {r["questionnaire"]["themes"][t] for t in ("dividende", "devise_etrangere", "action_individuelle")} == {"neutre"}
    for p in ("amira", "mateo", "robert"):
        q = api.lire_fiche_client(p)["questionnaire"]["themes"]
        assert q["dividende"] == q["devise_etrangere"] == q["action_individuelle"] == "neutre"


def test_exclure_les_dividendes_rend_l_achat_incompatible():
    r = api.simuler_ordre(_client(dividende="exclure"), "RY.TO", "achat", 5)
    assert r["verdict"]["code"] == "incompatible"
    assert r["contraintes_strictes"]["themes_violes"] == ["dividende"]
    assert api.simuler_ordre(_client(dividende="exclure"), "SHOP.TO", "achat", 2)["verdict"]["code"] != "incompatible"


def test_obligatoire_actions_individuelles_refuse_un_fonds():
    assert api.simuler_ordre(_client(action_individuelle="obligatoire"), "QQQ", "achat", 5)["verdict"]["code"] == "incompatible"
    assert api.simuler_ordre(_client(action_individuelle="obligatoire"), "RY.TO", "achat", 5)["verdict"]["code"] != "incompatible"


def test_eviter_la_devise_etrangere_mesure_le_poids_en_usd():
    r = api.simuler_ordre(_client(devise_etrangere="eviter"), "AAPL", "achat", 5)
    m = r["apres"]["notes"]["preferences"]["mesures"]["devise_etrangere"]
    assert m["poids_expose"] == pytest.approx(25.0)          # SPY 20 % + AAPL 5 %
    assert m["note"] == pytest.approx(max(0.0, 100 - 50 * 25 / 15))
