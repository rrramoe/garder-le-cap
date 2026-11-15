"""Fiche du client : le questionnaire et tout ce qui en est déduit (section 5)."""
from __future__ import annotations

import copy

from . import instruments, references


class ErreurClient(Exception):
    pass


CHAMPS = ("objectif", "horizon", "fluctuations", "capacite_perte", "besoin_liquidite", "experience")
DEFAUTS = {"besoin_liquidite": "aucun"}  # réponses neutres quand la fiche ne les donne pas

# Ordre des profils, du plus prudent au plus exposé : le profil retenu est le plus prudent
# de ce que le client accepte (fluctuations) et de ce que sa situation permet (capacité).
ORDRE_PROFILS = ("revenu", "conservateur", "equilibre", "croissance", "croissance_maximale")

# Hypothèse : profils jugés cohérents avec chaque objectif. Sert seulement à signaler
# une incohérence apparente ; n'entre pas dans le score.
COHERENCE_OBJECTIF = {
    "preserver_capital": ["revenu", "conservateur"],
    "revenu_regulier": ["revenu", "conservateur", "equilibre"],
    "croissance_equilibree": ["conservateur", "equilibre", "croissance"],
    "croissance_long_terme": ["equilibre", "croissance", "croissance_maximale"],
}

NIVEAU_DETAIL = {"debutante": "essentiel", "intermediaire": "standard", "avancee": "detaille"}


def _base(client) -> dict:
    """Retourne {'id', 'nom', 'questionnaire', 'portefeuille_pct'} à partir d'un id ou d'un dict."""
    personas = references.charger("personas")["personas"]
    if isinstance(client, str):
        cle = client.strip().lower()
        if cle not in personas:
            raise ErreurClient(f"Client inconnu : « {client} ». Personas disponibles : {', '.join(personas)}.")
        p = personas[cle]
        return {"id": cle, "nom": p["nom"], "questionnaire": copy.deepcopy(p["questionnaire"]),
                "portefeuille_pct": dict(p["portefeuille_pct"])}
    if not isinstance(client, dict):
        raise ErreurClient("Le client doit être un identifiant de persona ou une fiche (dictionnaire).")

    base_id = client.get("persona") or client.get("id")
    if base_id and str(base_id).lower() in personas:
        base = _base(str(base_id))
    else:
        base = {"id": base_id or "personnalise", "nom": client.get("nom", "Client"), "questionnaire": {"themes": {}},
                "portefeuille_pct": {}}
    q = dict(client.get("questionnaire", {}))
    # Réponse neutre par défaut : sans réponse explicite, la capacité suit les fluctuations.
    if "fluctuations" in q and "capacite_perte" not in q:
        q["capacite_perte"] = q["fluctuations"]
    for champ in CHAMPS:
        if champ in q:
            base["questionnaire"][champ] = q[champ]
    base["questionnaire"].setdefault("themes", {}).update(q.get("themes", {}))
    if "portefeuille_pct" in client:
        base["portefeuille_pct"] = {t: float(w) for t, w in client["portefeuille_pct"].items()}
    if "nom" in client:
        base["nom"] = client["nom"]
    return base


def decaler_liquidites(fourchettes: dict, besoin_pct: float) -> dict:
    """Relève le minimum, la cible et le maximum des liquidités du besoin de l'année (maximum plafonné à 100)."""
    f = copy.deepcopy(fourchettes)
    if besoin_pct:
        liq = f["liquidites"]
        liq["min"], liq["cible"] = liq["min"] + besoin_pct, liq["cible"] + besoin_pct
        liq["max"] = min(100, liq["max"] + besoin_pct)
    return f


def phrase_besoin(besoin_pct: float) -> str:
    if not besoin_pct:
        return "Aucun besoin de liquidités dans l'année : la zone des liquidités est celle du profil."
    return f"Vous gardez au moins {besoin_pct:g} % en liquidités pour vos besoins de l'année."


def construire_fiche(client) -> dict:
    b = _base(client)
    q = b["questionnaire"]
    if "fluctuations" in q:
        q.setdefault("capacite_perte", q["fluctuations"])
    for champ, defaut in DEFAUTS.items():
        q.setdefault(champ, defaut)
    ref_q = references.charger("questionnaire")
    for champ in CHAMPS:
        if champ not in q:
            raise ErreurClient(f"Réponse manquante au questionnaire : « {champ} ».")
        options = ref_q[champ]["options"]
        if q[champ] not in options:
            raise ErreurClient(f"Réponse invalide pour « {champ} » : « {q[champ]} ». Choix possibles : {', '.join(options)}.")

    themes_ref = references.charger("themes")["themes"]
    echelle = ref_q["echelle_themes"]["options"]
    themes = {}
    for t in themes_ref:
        rep = q["themes"].get(t["id"], "neutre")
        if rep not in echelle:
            raise ErreurClient(f"Réponse invalide pour le thème « {t['id']} » : « {rep} ». Choix possibles : {', '.join(echelle)}.")
        themes[t["id"]] = rep
    q["themes"] = themes

    # Portefeuille
    port = {t: float(w) for t, w in b["portefeuille_pct"].items() if float(w) != 0}
    if not port:
        raise ErreurClient("Le portefeuille est vide.")
    for t in port:
        instruments.fiche(t)  # lève si inconnu
        if port[t] < 0:
            raise ErreurClient(f"Poids négatif pour {t} : le portefeuille de départ ne contient que des positions positives. "
                               "Une vente à découvert se simule par un ordre (opération « decouvert »).")
    total = sum(port.values())
    if abs(total - 100) > 0.01:
        raise ErreurClient(f"Les poids du portefeuille totalisent {total:.2f} % au lieu de 100 %.")

    fluct = ref_q["fluctuations"]["options"][q["fluctuations"]]
    capa = ref_q["capacite_perte"]["options"][q["capacite_perte"]]
    profil_id = min(fluct["profil"], capa["profil"], key=ORDRE_PROFILS.index)
    profil = references.charger("profils")["profils"][profil_id]
    horizon = ref_q["horizon"]["options"][q["horizon"]]
    crypto = references.charger("crypto")["par_profil"][profil_id]
    besoin = ref_q["besoin_liquidite"]["options"][q["besoin_liquidite"]]
    fourchettes = decaler_liquidites(profil["fourchettes"], besoin["pct"])
    plafonds = references.charger("plafonds_concentration")["plafonds_pct"]

    contraintes = [{"theme": t, "reponse": r} for t, r in themes.items() if r in ("exclure", "obligatoire")]
    preferences = [{"theme": t, "reponse": r} for t, r in themes.items() if r in ("eviter", "rechercher")]

    profils_ref = references.charger("profils")["profils"]
    lib_accepte, lib_permis = profils_ref[fluct["profil"]]["libelle"], profils_ref[capa["profil"]]["libelle"]
    if fluct["profil"] == capa["profil"]:
        decide, phrase = "les_deux", f"Ce que vous acceptez et ce que votre situation permet donnent le même profil, {profil['libelle']}."
    elif profil_id == capa["profil"]:
        decide, phrase = "capacite", (f"Vous acceptez le profil {lib_accepte}, votre situation permet le profil {lib_permis} : "
                                      f"le plus prudent, {profil['libelle']}, est retenu.")
    else:
        decide, phrase = "fluctuations", (f"Vous acceptez le profil {lib_accepte}, votre situation permet le profil {lib_permis} : "
                                          f"le plus prudent, {profil['libelle']}, est retenu.")
    deduit = {
        "profil": {"valeur": profil_id, "libelle": profil["libelle"],
                   "origine": f"Fluctuations acceptées « {fluct['libelle']} » → profil {lib_accepte}. "
                              f"Capacité à supporter une perte « {capa['libelle']} » → profil {lib_permis}. "
                              "Le plus prudent des deux est retenu.",
                   "accepte": {"valeur": fluct["profil"], "libelle": lib_accepte},
                   "permis": {"valeur": capa["profil"], "libelle": lib_permis},
                   "decide_par": decide, "phrase": phrase,
                   "source": "fbngp_profils_2024", "regle": "acvm_capacite_perte", "hypothese": "hypothese_capacite_libelles"},
        "fourchettes_pct": {"valeur": fourchettes,
                            "origine": f"Fourchettes et cibles du profil {profil['libelle']}."
                                       + (f" Liquidités relevées de {besoin['pct']} points pour le besoin de l'année."
                                          if besoin["pct"] else ""),
                            "source": "fbngp_profils_2024",
                            **({"hypothese": "hypothese_besoin_liquidite"} if besoin["pct"] else {})},
        "besoin_liquidite_pct": {"valeur": besoin["pct"],
                                 "origine": f"Besoin de liquidités dans les 12 prochains mois « {besoin['libelle']} ».",
                                 "phrase": phrase_besoin(besoin["pct"]),
                                 "source": "questionnaire",
                                 **({"hypothese": "hypothese_besoin_liquidite"} if besoin["pct"] else {})},
        "horizon_annees": {"valeur": horizon["borne_basse_annees"],
                           "origine": f"Borne basse de l'horizon « {horizon['libelle']} ».", "source": "questionnaire"},
        "plafonds_concentration_pct": {"valeur": plafonds, "origine": "Plafonds identiques pour tous les profils.",
                                       "source": "fbngp_politique_2022", "hypothese": "hypothese_plafonds_tous_profils"},
        "crypto_pct": {"valeur": crypto, "origine": f"Cible et plafond (double de la cible) pour le profil {profil['libelle']}.",
                       "source": "fidelity_crypto_2026", "hypothese": "hypothese_crypto_correspondance"},
        "contraintes_strictes": {"valeur": contraintes, "origine": "Thèmes répondus « exclure » ou « obligatoire ».",
                                 "source": "questionnaire"},
        "preferences_souples": {"valeur": preferences, "origine": "Thèmes répondus « éviter » ou « rechercher ».",
                                "source": "questionnaire"},
        "niveau_detail": {"valeur": NIVEAU_DETAIL[q["experience"]],
                          "origine": f"Expérience « {ref_q['experience']['options'][q['experience']]} ».", "source": "questionnaire"},
        "coherence_objectif": {"valeur": "coherent" if profil_id in COHERENCE_OBJECTIF[q["objectif"]] else "a_verifier",
                               "origine": f"Objectif « {ref_q['objectif']['options'][q['objectif']]} » comparé au profil {profil['libelle']}. "
                                          "Signalement seulement, sans effet sur le score.",
                               "source": "hypothese_coherence_objectif"},
    }
    return {"id": b["id"], "nom": b["nom"], "questionnaire": q, "portefeuille_pct": port, "deduit": deduit}


def poids_par_classe(port: dict) -> dict:
    classes = {c: 0.0 for c in references.charger("profils")["classes"]}
    for t, w in port.items():
        c = references.classe_politique(t)
        classes[c] = classes.get(c, 0.0) + w
    return classes
