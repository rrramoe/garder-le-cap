"""Mots et formats de l'interface, en un seul endroit : un mot pour une chose.

Tous les chiffres viennent de moteur.api ; ce module ne fait que les nommer et les mettre en forme.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from moteur import api, references

# Le nom du service, son descripteur et le titre de l'onglet : en un seul endroit. Changer le nom = changer NOM.
NOM = "Sigma"
DESCRIPTEUR = "Gestion des risques"
SENS_DU_NOM = "σ, sigma : le symbole du risque en finance."

BANDEAU = ("Simulation à but éducatif. Aucune transaction réelle. "
           "Ceci n'est pas un conseil financier personnalisé.")
AVIS_SANS_AGENT = ("Explication de l'agent indisponible : l'analyse ci-dessous vient "
                   "directement du moteur de calcul")
LIMITE = api.NOTE_DE_PASSAGE  # note de passage : fixée par le moteur, jamais ici

BOUTON_ACTION = "Analyser l'ordre"
BOUTON_PASSER = "Passer l'ordre (simulé)"
TITRE_ANALYSE = "Analyse de l'ordre"
TITRE_ETAPES = "Étapes de l'analyse"
DEPUIS_PRECEDENT = "Depuis l'analyse précédente"
EN_DIRECT_AGENT = "Analyse en cours"
DEJA_FAITE = "Analyse déjà faite pour cet ordre."
TRACE = "Analyse n° {id} · trace conservée"
TRACE_AIDE = ("Chaque analyse laisse une trace : l'ordre, chaque calcul demandé au moteur, les contrôles, la durée. "
              "Aucune donnée personnelle n'y figure.")
DELAI_MAX_AGENT_S = 240  # au-delà, l'analyse du moteur reste seule affichée

# Les destinations, dans l'ordre du parcours : la fiche et la politique, le portefeuille, l'ordre, l'aide.
PAGES = {"profil": "Profil", "portefeuille": "Portefeuille", "negocier": "Négocier", "aide": "Aide"}

NOMS_AGENTS = {"principal": "Agent principal", "explorateur": "Agent explorateur"}
LIBELLES_OUTILS = {
    "lire_fiche_client": "Je lis votre profil.",
    "lire_fiche_instrument": "Je lis la fiche du titre.",
    "decrire_apport": "Je regarde ce que le titre apporterait à votre portefeuille.",
    "simuler_ordre": "Je simule l'ordre sur votre portefeuille.",
    "simuler_scenario": "Je teste une combinaison d'ordres.",
    "chercher_taille_compatible": "Je cherche le montant compatible.",
    "lister_instruments": "Je cherche des titres proches.",
    "envoyer_explorateur": "J'envoie l'explorateur chercher des pistes.",
    "juger_pistes": "Je juge les pistes testées.",
    "corriger_le_texte": "Je corrige mon texte après vérification.",
}
LIBELLES_PHASES = {
    "redaction": "Je rédige l'explication.",
    "verification": "Je vérifie mon texte.",
    "correction": "Je corrige mon texte.",
}

# L'introduction, montrée une fois à l'ouverture : une présentation du produit, pas un mode d'emploi.
# Tous ses mots sont ici. Par panneau : la vue, le titre, une ou deux phrases, et au plus un essentiel
# technique, dit à voix basse. {nom}, {montant} et {titre} sont remplis avec l'ordre prêt d'un compte enregistré.
INTRODUCTION = [
    ("ecart", "Les professionnels ont un département de risque. Le particulier n'a que son enthousiasme.",
     [NOM + " vous donne le vôtre : à chaque ordre, il mesure l'écart avec votre politique de placement "
      "et vos objectifs, avant que vous ne le passiez."],
     SENS_DU_NOM),
    ("fiche", "Quelques réponses. Une politique de placement.",
     ["Votre objectif, votre horizon, la perte que vous pouvez absorber : votre fiche devient des limites claires, "
      "chacune avec sa source."],
     ""),
    ("issues", "Avant de passer l'ordre, mettez-le à l'épreuve.",
     ["Il respecte votre politique, il vous en fait sortir, ou il vous en rapproche : vous le savez avant d'acheter."],
     ""),
    ("resultat", "Cinq angles. Un verdict. Et le pourquoi.",
     ["Objectif, risque, liquidité, diversification, préférences : l'angle le plus bas décide.",
      "Deux agents expliquent le résultat et testent ce qui serait possible."],
     "Chaque chiffre est calculé par le code, jamais par le modèle."),
    ("billet", "{nom} veut {montant} de {titre}. Qu'en dit sa politique ?",
     ["Choisissez un compte et tentez un ordre.",
      "Le service renseigne, il ne conseille jamais ; c'est une simulation, sans transaction réelle."],
     ""),
]
INTRO_SUIVANT, INTRO_RETOUR, INTRO_FIN, INTRO_REPRENDRE = "Suivant", "Retour", "Choisir un compte", "Reprendre"
# Le chemin d'un compte, montré au moment de le choisir.
CHEMIN = [("Profil", "Votre fiche devient votre politique de placement."),
          ("Portefeuille", "Où vous en êtes, sous chaque angle."),
          ("Négocier", "Analysez un ordre avant de le passer.")]
BOUTON_PASSER_INTRO = "Passer l'introduction"
BOUTON_ESSAI = "Analyser tout de suite un ordre d'exemple"
# Comment le service fonctionne, en mots simples. Rien n'est dit ici qui ne soit construit.
FONCTIONNEMENT = [
    ("Votre fiche", "Quatorze réponses : votre objectif, votre horizon, le risque que vous acceptez et celui que "
                    "votre situation permet, vos contraintes, vos préférences."),
    ("Votre politique de placement", "Le service la tire de votre fiche : un profil, une répartition par classe "
                                     "d'actif, des limites. Chaque limite vient d'une source publiée, ou porte la "
                                     "marque « hypothèse »."),
    ("Cinq angles", "Avant de passer un ordre, le service le note sous chaque angle : objectif, risque, liquidité, "
                    "diversification, préférences. L'angle le plus bas décide du verdict."),
    ("Le code calcule", "Chaque note, chaque verdict et chaque piste testée vient du moteur de calcul. "
                        "Aucun chiffre ne vient d'un modèle de langage."),
    ("Deux agents expliquent", "Le premier lit votre cas, dirige la recherche et rédige l'explication. "
                               "Le second cherche et teste des pistes. Ils ne conseillent rien."),
    ("Un garde-fou", "Il refuse le conseil personnalisé et les transactions réelles, et vérifie que "
                     "l'explication s'appuie sur les calculs."),
]
SERVICES_AWS = [
    ("Amazon Bedrock", "Le modèle de langage des deux agents."),
    ("Strands Agents", "Le kit qui donne aux agents leurs outils : les appels au moteur de calcul."),
    ("Amazon Bedrock Guardrails", "Le garde-fou : refus du conseil et des transactions, contrôle de l'explication."),
    ("Amazon S3", "Un espace privé qui garde les fichiers de référence."),
    ("Amazon EC2", "La machine qui sert cette application."),
    ("Amazon CloudFront", "L'adresse sécurisée (HTTPS) par laquelle on atteint l'application."),
]
MISSION = f"Un placement est un moyen. Pas un objectif. {NOM} renseigne, il ne conseille pas."

# Clients enregistrés : les trois exemples de l'énoncé ont la même forme qu'un nouveau client.
EXEMPLES_ENREGISTRES = [
    {"id": "robert", "valeur": 800_000,
     "description": "59 ans, proche de la retraite"},
    {"id": "mateo", "valeur": 250_000, "description": "41 ans, deux enfants"},
    {"id": "amira", "valeur": 50_000, "description": "26 ans, début de carrière"},
]
NOUVEAU = "nouveau"
VALEUR_NOUVEAU = 100_000

# Opérations et types d'ordre. Ajouter une opération revient à ajouter une entrée ici.
OPERATIONS = {
    "achat": {"libelle": "Acheter", "nom": "Achat", "sens": "achat"},
    "vente": {"libelle": "Vendre", "nom": "Vente", "sens": "vente"},
    "marge": {"libelle": "Acheter sur marge", "nom": "Achat sur marge", "sens": "achat", "operation": "marge",
              "aide": "Opération avancée : l'achat peut dépasser vos liquidités. La différence est empruntée."},
    "decouvert": {"libelle": "Vendre à découvert", "nom": "Vente à découvert", "sens": "vente",
                  "operation": "decouvert",
                  "aide": "Opération avancée : vous vendez un titre emprunté, que vous ne détenez pas."},
}
MESURES_OPERATION = {"achat_sur_marge": "argent emprunté", "vente_a_decouvert": "titres vendus à découvert"}
TYPES_ORDRE = {
    "marche": {"libelle": "Au marché", "prix": None, "aide": "Exécuté tout de suite, au prix du moment."},
    "limite": {"libelle": "À cours limité", "prix": "Prix limite ($ CA)",
               "aide": "Exécuté seulement à ce prix ou mieux."},
    "stop": {"libelle": "Stop", "prix": "Prix de déclenchement ($ CA)",
             "aide": "Devient un ordre au marché quand le prix atteint ce seuil."},
}

CLASSES = {"liquidites": "Liquidités", "revenu_fixe": "Revenu fixe", "actions": "Actions",
           "alternatifs": "Titres alternatifs"}
# Un angle : son nom, et son nom dans une phrase.
ANGLES = {"objectif": ("Objectif", "l'objectif"), "risque": ("Risque", "le risque"),
          "liquidite": ("Liquidité", "la liquidité"), "diversification": ("Diversification", "la diversification"),
          "preferences": ("Préférences", "les préférences")}
ANGLES_DEFAUT = tuple(ANGLES)
AIDE_ANGLES = {
    "objectif": "Ce que l'ordre fait pour votre objectif.",
    "risque": "La perte qui peut être absorbée, d'après le passé.",
    "liquidite": "L'argent dont vous aurez besoin dans l'année.",
    "diversification": "Varier les expositions : ne pas dépendre d'un seul titre, d'un seul secteur ou d'un seul pays.",
    "preferences": "Les thèmes que vous voulez éviter ou rechercher.",
}
MESURES = {
    "capital_preserve": "capital préservé sur l'horizon",
    "revenu": "revenu du portefeuille",
    "actions": "part des actions face à votre objectif",
    "fluctuations": "fluctuations",
    "pire_annee": "pire année",
    "liquidites_besoin": "liquidités face à votre besoin",
    "geographie_actions": "répartition des actions, Canada et ailleurs",
    "ampleur": "pire baisse",
    "duree": "temps pour se remettre d'une baisse",
    "classe_liquidites": "part des liquidités",
    "classe_revenu_fixe": "part du revenu fixe",
    "classe_actions": "part des actions",
    "classe_alternatifs": "part des titres alternatifs",
    "crypto": "part des cryptoactifs",
    "plus_grosse_action": "plus grosse action",
    "plus_gros_fonds": "plus gros fonds",
    "plus_gros_secteur": "plus gros secteur",
}
SECTEURS = {
    "Communication Services": "Services de communication",
    "Consumer Discretionary": "Consommation discrétionnaire",
    "Consumer Staples": "Consommation de base",
    "Energy": "Énergie",
    "Financials": "Services financiers",
    "Health Care": "Santé",
    "Industrials": "Industrie",
    "Information Technology": "Technologies de l'information",
    "Utilities": "Services publics",
}
DIRECTIONS_TEXTE = {
    "reste_dans_la_politique": "Votre portefeuille reste dans votre politique de placement.",
    "fait_sortir_de_la_politique": "Votre portefeuille sortirait de votre politique de placement.",
    "hors_politique_rapproche": "Votre portefeuille est déjà hors de votre politique de placement ; l'ordre l'en rapproche.",
    "hors_politique_aggrave": "Votre portefeuille est déjà hors de votre politique de placement ; l'ordre creuse l'écart.",
    "revient_dans_la_politique": "Votre portefeuille est hors de votre politique de placement ; l'ordre l'y ramène.",
    "hors_politique_inchange": "Votre portefeuille est déjà hors de votre politique de placement ; "
                               "l'ordre ne change pas son angle déterminant.",
}
# Où l'ordre mène, en quelques mots (introduction) ; un cas inconnu garde le libellé du moteur.
ISSUES = {
    "reste_dans_la_politique": "Il reste dans la politique",
    "fait_sortir_de_la_politique": "Il fait sortir de la politique",
    "hors_politique_rapproche": "Il rapproche de la politique",
    "hors_politique_aggrave": "Il éloigne encore de la politique",
    "revient_dans_la_politique": "Il ramène dans la politique",
    "hors_politique_inchange": "Il ne change pas l'écart",
}
ISSUE_REGLE = "Il touche une règle stricte"
STATUTS_REGLE = {"violee": "non respectée", "respectee": "respectée", "signalee": "signalée",
                 "ignoree": "ignorée", "non_applicable": "sans objet"}
SOLIDITE_TEXTE = {
    "solide": "le résultat est le même dans une année de forte baisse comme dans les autres.",
    "fragile": "le résultat change selon qu'on regarde une année de forte baisse ou les autres.",
}
VERIFICATION_TEXTE = {
    "appuyee": "Vérifié : chaque chiffre de ce texte vient des calculs.",
    "non_appuyee": "À lire avec prudence : une partie de ce texte ne correspond pas aux calculs. "
                   "Fiez-vous aux chiffres de l'analyse.",
}
CORRECTION_TEXTE = "L'agent a corrigé son texte après vérification."
VERDICTS_AIDE = [("compatible", "Compatible", "L'ordre respecte votre politique de placement."),
                 ("en_tension", "En tension", "L'ordre dépasse une limite de votre politique de placement."),
                 ("incompatible", "Incompatible", "L'ordre touche une règle stricte de votre profil.")]


# ---------------------------------------------------------------- références

@st.cache_data
def charger_reference(nom: str) -> dict:
    return references.charger(nom)  # bucket S3 privé s'il est configuré, sinon dossier reference/


QUESTIONNAIRE = charger_reference("questionnaire")
THEMES = {t["id"]: t["libelle"] for t in charger_reference("themes")["themes"]}
CHAMPS_Q = ("objectif", "horizon", "fluctuations", "capacite_perte", "besoin_liquidite", "experience")
PERSONAS = charger_reference("personas")["personas"]
# Le formulaire du profil, sous les cinq rubriques du profil d'investisseur : objectif, horizon, risque,
# contraintes, préférences (les thèmes). Une question absente de ces rubriques va sous « Contraintes ».
RUBRIQUES = {"objectif": ("Objectif", "Pourquoi investir ?"),
             "horizon": ("Horizon", "Quand l'argent sera-t-il requis ?"),
             "risque": ("Risque", "Quelle perte peut être absorbée ?"),
             "contraintes": ("Contraintes", "Ce qui limite les choix."),
             "preferences": ("Préférences", "Ce qui compte pour vous.")}
GROUPES_Q = [("objectif", ("objectif",)), ("horizon", ("horizon",)),
             ("risque", ("fluctuations", "capacite_perte")),
             ("contraintes", ("besoin_liquidite", "experience"))]
PHRASE_LIMITES = ("Les contraintes établissent les limites. Les préférences orientent les choix "
                  "à l'intérieur de ces limites.")


@st.cache_data
def instruments() -> dict:
    r = api.lister_instruments()
    return {i["symbole"]: i for i in r.get("instruments", [])}


@st.cache_data
def derniers_prix_cad() -> dict:
    """Dernier prix connu de chaque titre, en dollars canadiens (lecture seule des données du moteur)."""
    try:
        from moteur import donnees
        p = donnees.prix_cad()
        return {t: float(v) for t, v in p.ffill().iloc[-1].items() if pd.notna(v)}
    except Exception:
        return {}


# ---------------------------------------------------------------- formats

def nombre(x: float, d: int = 1) -> str:
    texte = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return texte.replace("-", "−")


def pct(x: float, d: int = 1) -> str:
    """x est déjà en % (15 = 15 %)."""
    return f"{nombre(x, d)} %"


def pct_frac(x: float, d: int = 1) -> str:
    """x est une fraction (−0,18 = −18 %)."""
    return pct(x * 100, d)


def dollars(x: float, d: int = 0) -> str:
    return f"{nombre(x, d)} $"


def annees(x: float, d: int = 1) -> str:
    """« 0,5 an », « 1 an », « 2,5 ans »."""
    return f"{nombre(x, d)} an" + ("s" if abs(x) >= 2 else "")


def note_txt(x: float | None) -> str:
    return "—" if x is None else nombre(x, 0)


def libelle_option(champ: str, cle: str) -> str:
    opt = QUESTIONNAIRE[champ]["options"][cle]
    return opt if isinstance(opt, str) else opt["libelle"]


def libelle_theme_reponse(cle: str) -> str:
    return QUESTIONNAIRE["echelle_themes"]["options"][cle]["libelle"]


def nom_angle(cle: str) -> str:
    return ANGLES.get(cle, (str(cle).replace("_", " ").capitalize(), ""))[0]


def angle_en_phrase(cle: str) -> str:
    return ANGLES.get(cle, ("", str(cle).replace("_", " ")))[1]


def libelle_mesure(angle: str, cle: str) -> str:
    if angle == "preferences":
        if cle in MESURES_OPERATION:
            return MESURES_OPERATION[cle]
        return f"thème « {THEMES.get(cle, cle)} »"
    return MESURES.get(cle, str(cle).replace("_", " "))


def nom_instrument(ticker: str) -> str:
    i = instruments().get(ticker)
    return f"{ticker} ({i['nom']})" if i else ticker


def nom_agent(code: str) -> str:
    return NOMS_AGENTS.get(code, f"Agent {code}")


# Les mots des fichiers de référence et du moteur, ramenés à ceux de l'interface : un mot pour une chose.
_MOTS = [(r"\bsur le score\b", "sur la note"), (r"\b[Ll]e score\b", "la note"), (r"\bdu score\b", "de la note"),
         (r"\bscores?\b", "note"), (r"\bla famille\b", "l'angle"), (r"\bFamilles?\b", "Angle"),
         (r"\bfamilles\b", "angles"), (r"\bfamille\b", "angle"), (r"\bdimensions?\b", "angle"),
         (r"\bchaque persona\b", "chaque client d'exemple"), (r"\bpersonas?\b", "client d'exemple"),
         (r"\s*\((?:moteur/[^)]*|spécification[^)]*|simplification)\)", ""),
         (r"\s*\(voir [\w./]+\.json\)", "")]


def francais(texte: str) -> str:
    """Une phrase du moteur ou d'un fichier de référence, avec les mots de l'interface et le vrai signe moins."""
    import re
    texte = re.sub(r"(?<![\w,])-(?=\d)", "−", str(texte))
    for motif, mot in _MOTS:
        texte = re.sub(motif, mot, texte)
    return texte


def decrire_mesure(angle: str, cle: str, m: dict) -> str:
    """Une phrase courte avec les chiffres d'une mesure, tels que le moteur les donne."""
    if m.get("statut") in ("indetermine", "sans_objet"):
        return "inconnu" if m["statut"] == "indetermine" else "sans objet"
    if m.get("phrase"):
        return francais(m["phrase"])
    if cle == "ampleur" and angle == "risque":
        return (f"pire baisse passée {pct_frac(m['pire_baisse'])} ; "
                f"limite du profil {pct_frac(m['pire_baisse_limite'])}")
    if cle == "duree" and angle == "risque":
        texte = (f"{annees(m['temps_sous_l_eau_annees'])} pour se remettre, "
                 f"pour un horizon de {annees(m['horizon_annees'], 0)}")
        if m.get("non_recupere"):
            texte += " ; pas encore remis"
        return texte
    if cle.startswith("classe_") and "poids" in m:
        return f"{pct(m['poids'])} ; permis : {nombre(m['min'], 0)} à {pct(m['max'], 0)}"
    if cle == "crypto" and angle == "diversification":
        return f"{pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if cle in ("plus_grosse_action", "plus_gros_fonds"):
        if not m.get("ticker"):
            return "aucune"
        return f"{m['ticker']} : {pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if cle == "plus_gros_secteur":
        if not m.get("secteur"):
            return "aucune action seule"
        return f"{SECTEURS.get(m['secteur'], m['secteur'])} : {pct(m['poids'])} ; maximum {pct(m['plafond'], 0)}"
    if angle == "preferences":
        if m.get("operation") and "poids_expose" in m:
            return f"{pct(m['poids_expose'])} du portefeuille ; repère de 15 %"
        if "poids_expose" in m:
            texte = f"{pct(m['poids_expose'])} du portefeuille dans ce thème à éviter"
            if m.get("etiquette_indeterminee"):
                texte += " (inconnu pour " + ", ".join(m["etiquette_indeterminee"]) + ")"
            return texte
        if "poids_vendu" in m:
            return f"{pct(m['poids_vendu'])} vendu dans ce thème recherché"
    return ""


def phrase_angle_determinant(mes: str, m: dict) -> str | None:
    """Une phrase courte pour l'angle déterminant ; les chiffres complets restent dans les mesures repliées."""
    v, lim = m.get("valeur"), m.get("limite")
    if not isinstance(v, (int, float)):
        return None
    try:
        if mes == "pire_annee":
            return (f"L'angle déterminant : la pire année. Votre portefeuille aurait perdu {pct_frac(abs(v))} "
                    f"en un an, pour une limite de {pct_frac(abs(lim))}.") if v < 0 else None
        if mes == "fluctuations":
            return (f"L'angle déterminant : les fluctuations. Elles seraient de {pct_frac(v)} par an, "
                    f"pour une limite de {pct_frac(lim)}.")
        if mes == "geographie_actions":
            quoi = "canadiennes" if m.get("decide") == "canada" else "hors du Canada"
            return (f"L'angle déterminant : la répartition des actions. Les actions {quoi} feraient {pct(v)} "
                    f"du portefeuille, pour une zone de {pct(m['limite_basse'], 0)} à {pct(m['limite_haute'], 0)}.")
        if mes == "capital_preserve":
            return (f"L'angle déterminant : préserver votre capital. Sur {annees(m['fenetre_annees'], 0)}, "
                    f"le pire résultat aurait été {pct_frac(v)}.")
        if mes == "revenu":
            return (f"L'angle déterminant : le revenu. Votre portefeuille rapporterait {pct_frac(v, 2)} par an, "
                    f"pour une limite de {pct_frac(lim, 2)}.")
        if mes == "actions":
            return (f"L'angle déterminant : la part des actions pour votre objectif, {pct(v)}, "
                    f"pour un minimum de {pct(lim, 0)}.")
        if mes == "liquidites_besoin":
            return (f"L'angle déterminant : vos liquidités, {pct(v)}, pour un besoin de "
                    f"{pct(m.get('besoin', lim), 0)} dans l'année.")
    except (KeyError, TypeError):
        return None
    return None


def raison_courte(sim: dict) -> str:
    """Une phrase claire qui dit pourquoi, à partir de l'angle déterminant et de sa mesure la plus basse."""
    if sim["verdict"]["code"] == "incompatible":
        detail = sim["contraintes_strictes"].get("detail", [])
        ce = (sim.get("operation") or {}).get("controle_experience", {})
        if any(d.get("controle") == "experience_operation" and d["statut"] == "violee" for d in detail):
            return (f"La {sim['operation']['libelle'].lower()} est exclue pour l'expérience "
                    f"« {libelle_option('experience', ce.get('experience', 'debutante'))} ». "
                    "C'est une règle stricte.")
        violees = [THEMES.get(d["theme"], d["theme"]) for d in detail if d["statut"] == "violee"]
        if violees:
            return (f"Ce titre touche un thème que vous excluez : {', '.join(violees)}. "
                    "C'est une règle stricte de votre profil.")
        return "Une règle stricte de votre profil n'est pas respectée."
    angle, mes = sim["dimension_min"], sim["mesure_min"]
    m = sim["apres"]["notes"][angle]["mesures"].get(mes, {})
    if mes == "ampleur":
        verbe = "dépasserait" if sim["score"] < LIMITE else "resterait sous"
        return (f"Dans le passé, la pire baisse du portefeuille aurait été de {pct_frac(m['pire_baisse'], 0)}. "
                f"Elle {verbe} la limite de votre profil ({pct_frac(m['pire_baisse_limite'], 0)}).")
    if mes == "duree":
        return (f"Après une baisse, le portefeuille aurait mis {annees(m['temps_sous_l_eau_annees'])} "
                f"à se remettre, pour un horizon de {annees(m['horizon_annees'], 0)}.")
    phrase = phrase_angle_determinant(mes, m)
    if phrase:
        return phrase
    detail = decrire_mesure(angle, mes, m)
    return f"L'angle déterminant : {libelle_mesure(angle, mes)}" + (f" — {detail}." if detail else ".")


def mesures_a_plat(bloc: dict) -> dict:
    """{(angle, mesure): note} pour comparer deux analyses."""
    sortie = {}
    for angle, n in bloc.get("notes", {}).items():
        for cle, m in n.get("mesures", {}).items():
            if isinstance(m, dict) and "note" in m:
                sortie[(angle, cle)] = m["note"]
    return sortie


def angles_du_bloc(bloc: dict) -> list:
    return [f for f in bloc.get("familles", ANGLES_DEFAUT) if f in bloc.get("notes", {})]


def phrase_execution(type_ordre: str, prix: float | None) -> str:
    if type_ordre == "marche" or prix is None:
        return "L'analyse suppose que l'ordre est exécuté au prix du moment."
    return f"L'analyse suppose que l'ordre est exécuté à {dollars(prix, 2)}."


# Le nom court d'un organisme, tel qu'on le cite après un article de la politique de placement.
NOMS_COURTS = {"Financière Banque Nationale – Gestion de patrimoine": "Banque Nationale",
               "FBN Gestion de patrimoine": "Banque Nationale",
               "Autorités canadiennes en valeurs mobilières": "ACVM"}


def source_courte(s: dict | None) -> str:
    """Le nom d'une source en quelques mots : l'organisme, sans le détail du document."""
    if not s:
        return ""
    nom = str(s.get("source", "")).split(",")[0].split("(")[0].strip()
    return NOMS_COURTS.get(nom, nom)
