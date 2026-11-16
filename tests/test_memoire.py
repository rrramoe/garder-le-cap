"""Mémoire des analyses : partage d'une analyse en cours, rejeu d'une analyse finie (modèle simulé)."""
import threading
import time

import pytest

from agent import inspection, memoire
from moteur import donnees
from tests.test_agent import SCENARIO_ROBERT, ModeleSimule

pytestmark = pytest.mark.skipif(
    not (donnees.dossier_donnees() / "prices_daily.csv").exists(),
    reason="data/prices_daily.csv absent : régénérez-le avec data/build_dataset.py",
)


@pytest.fixture(autouse=True)
def memoire_vide(tmp_path, monkeypatch):
    monkeypatch.setenv("GLC_MEMOIRE_FICHIER", str(tmp_path / "analyses.json"))
    memoire.oublier()
    yield
    memoire.oublier()


class ModeleLentUnPeu(ModeleSimule):
    async def stream(self, *args, **kwargs):
        import asyncio
        await asyncio.sleep(0.3)
        async for x in super().stream(*args, **kwargs):
            yield x


def _analyser(modele, ticker="TSLA", pourcentage=15, evenements=None, **options):
    return inspection.inspecter("robert", ticker, "achat", pourcentage, modele=modele, equipe=False, memoire=True,
                                sur_etape=(evenements.append if evenements is not None else None), **options)


def test_deux_demandes_simultanees_une_seule_analyse():
    modele = ModeleLentUnPeu(SCENARIO_ROBERT)
    resultats, evenements = [None, None], [[], []]

    def lancer(i):
        resultats[i] = _analyser(modele, evenements=evenements[i])
    fils = [threading.Thread(target=lancer, args=(i,)) for i in (0, 1)]
    fils[0].start()
    time.sleep(0.2)
    fils[1].start()
    for f in fils:
        f.join(30)
    assert modele.appels == len(SCENARIO_ROBERT)                     # un seul passage du modèle
    assert {r["memoire"]["statut"] for r in resultats} == {"nouvelle", "partagee"}
    assert resultats[0]["explication"] == resultats[1]["explication"]
    assert [e["moment"] for e in evenements[0]] == [e["moment"] for e in evenements[1]]   # étapes rejouées


def test_analyse_finie_rejouee_vite_avec_ses_etapes():
    premier = _analyser(ModeleSimule(SCENARIO_ROBERT))
    assert premier["memoire"] == {"statut": "nouvelle"}
    modele, evenements = ModeleSimule(SCENARIO_ROBERT), []
    debut = time.monotonic()
    second = _analyser(modele, evenements=evenements)
    assert time.monotonic() - debut < 1 and modele.appels == 0
    assert second["memoire"]["statut"] == "deja_faite" and "déjà faite" in second["memoire"]["message"]
    assert second["explication"] == premier["explication"] and second["trace"] == premier["trace"]
    assert [e["moment"] for e in evenements][-1] == "fin" and any(e["moment"] == "debut_outil" for e in evenements)


def test_autre_ordre_ou_autre_fiche_refait_l_analyse():
    _analyser(ModeleSimule(SCENARIO_ROBERT))
    modele = ModeleSimule(SCENARIO_ROBERT)
    assert _analyser(modele, pourcentage=10)["memoire"]["statut"] == "nouvelle" and modele.appels > 0
    autre = {"persona": "robert", "questionnaire": {"horizon": "15_plus"}}
    modele = ModeleSimule(SCENARIO_ROBERT)
    r = inspection.inspecter(autre, "TSLA", "achat", 15, modele=modele, equipe=False, memoire=True)
    assert r["memoire"]["statut"] == "nouvelle" and modele.appels > 0


def test_analyse_en_echec_non_gardee_et_relancer():
    from botocore.exceptions import ClientError
    e = ClientError({"Error": {"Code": "ThrottlingException", "Message": "trop"}}, "ConverseStream")
    assert _analyser(ModeleSimule([], erreur=e))["erreur"]
    modele = ModeleSimule(SCENARIO_ROBERT)
    assert _analyser(modele)["memoire"]["statut"] == "nouvelle" and modele.appels > 0     # l'échec n'a pas été gardé
    modele = ModeleSimule(SCENARIO_ROBERT)
    assert _analyser(modele, relancer=True)["memoire"]["statut"] == "nouvelle" and modele.appels > 0


def test_memoire_partagee_entre_processus_par_le_fichier():
    _analyser(ModeleSimule(SCENARIO_ROBERT))
    memoire.oublier()                                  # un autre processus : rien en mémoire, le fichier reste
    modele = ModeleSimule(SCENARIO_ROBERT)
    assert _analyser(modele)["memoire"]["statut"] == "deja_faite" and modele.appels == 0


def test_taille_bornee(monkeypatch):
    monkeypatch.setattr(memoire, "TAILLE_MAX", 2)
    for pct in (5, 6, 7):
        _analyser(ModeleSimule(SCENARIO_ROBERT), pourcentage=pct)
    assert len(memoire._finies) == 2


def test_sans_memoire_par_defaut_pour_un_modele_simule():
    r = inspection.inspecter("robert", "TSLA", "achat", 15, modele=ModeleSimule(SCENARIO_ROBERT), equipe=False)
    assert r["memoire"] is None


def test_autre_reponse_du_moteur_refait_l_analyse(monkeypatch):
    _analyser(ModeleSimule(SCENARIO_ROBERT))
    vrai = inspection._api_moteur.simuler_ordre

    def autre(*args, **kwargs):            # même demande, mais le moteur répond un autre chiffre
        r = vrai(*args, **kwargs)
        return {**r, "score": (r.get("score") or 0) + 1}
    monkeypatch.setattr(inspection._api_moteur, "simuler_ordre", autre)
    modele = ModeleSimule(SCENARIO_ROBERT)
    assert _analyser(modele)["memoire"]["statut"] == "nouvelle" and modele.appels > 0


def test_pas_de_memoire_si_le_moteur_ne_repond_pas(monkeypatch):
    monkeypatch.setattr(inspection._api_moteur, "chercher_taille_compatible", lambda *a, **k: {"erreur": "x"})
    assert _analyser(ModeleSimule(SCENARIO_ROBERT))["memoire"] is None


def test_auditeur_sans_resultat_fait_sa_propre_analyse():
    commence = threading.Event()

    def proprietaire(diffuser):
        commence.set()
        time.sleep(0.3)
        raise RuntimeError("panne")

    erreurs, resultats = [], []

    def lancer_proprietaire():
        try:
            memoire.partager("cle-essai", proprietaire)
        except RuntimeError as e:
            erreurs.append(e)
    fil = threading.Thread(target=lancer_proprietaire)
    fil.start()
    commence.wait(5)
    debut = time.monotonic()
    r = memoire.partager("cle-essai", lambda diffuser: {"explication": "ok", "erreur": None})
    fil.join(5)
    assert erreurs and time.monotonic() - debut < 5                      # pas d'attente de 300 s
    assert r["explication"] == "ok" and r["memoire"]["statut"] == "nouvelle"


def test_ancienne_analyse_sans_trace_rejouee_sans_casser(tmp_path, monkeypatch):
    # Une entrée écrite avant l'ajout des traces (sans `trace_aws`) dans le vrai fichier de mémoire.
    import json
    r = _analyser(ModeleSimule(SCENARIO_ROBERT))
    fichier = memoire.fichier()
    donnees = json.loads(fichier.read_text(encoding="utf-8"))
    for entree in donnees.values():
        entree["resultat"].pop("trace_aws", None)
    fichier.write_text(json.dumps(donnees), encoding="utf-8")
    memoire.oublier()
    rejoue = _analyser(ModeleSimule(SCENARIO_ROBERT))
    assert rejoue["memoire"]["statut"] == "deja_faite" and rejoue["trace_aws"] is None
    assert rejoue["explication"] == r["explication"]
