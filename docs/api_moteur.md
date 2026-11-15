# API du moteur

Point d'entrée unique : `moteur/api.py`. L'agent et l'interface n'appellent que ces fonctions.

```python
from moteur import api
api.simuler_ordre("robert", "TSLA", "achat", 15)
```

**Règles communes**

- Chaque fonction renvoie un dictionnaire sérialisable en JSON avec un champ `sources` : une liste de `{id, libelle, source, date, nature}`, où `nature` vaut `publie` ou `hypothese`.
- En cas de problème : `{"erreur": "message en français"}` et rien d'autre. Aucune exception ne sort de l'API.
- **Client** : un identifiant de persona (`"robert"`, `"mateo"`, `"amira"`) ou une fiche (dictionnaire). Une fiche peut partir d'un persona et modifier des réponses : `{"persona": "robert", "questionnaire": {"horizon": "15_plus", "themes": {"crypto": "exclure"}}}`. On peut aussi remplacer `portefeuille_pct`. Une fiche renvoyée par `lire_fiche_client` est acceptée telle quelle.
- **Sens** : `"achat"` ou `"vente"`. **Pourcentage** : en % du portefeuille (15 = 15 %). Un achat est payé par l'encaisse (`ZST.TO`), une vente y est versée. Pas de marge : un achat plus gros que l'encaisse renvoie une erreur.
- Les notes vont de 0 à 100 (100 = sur la cible, 50 = limite de la politique). Les pires baisses sont des fractions négatives (−0,18 = −18 %). Les poids sont en %.
- Les réponses possibles au questionnaire sont dans `reference/questionnaire.json` (`objectif`, `horizon`, `fluctuations`, `experience`, et l'échelle des thèmes `exclure / eviter / neutre / rechercher / obligatoire`). Les thèmes sont dans `reference/themes.json`.

## `lire_fiche_client(client)`

| Champ | Contenu |
|---|---|
| `id`, `nom` | Identifiant et nom |
| `questionnaire` | Les 9 réponses : `objectif`, `horizon`, `fluctuations`, `experience`, `themes` (5 thèmes) |
| `portefeuille_pct` | Positions, ticker → % |
| `poids_par_classe_pct` | `liquidites`, `revenu_fixe`, `actions`, `alternatifs` |
| `deduit` | `profil`, `fourchettes_pct`, `horizon_annees`, `plafonds_concentration_pct`, `crypto_pct`, `contraintes_strictes`, `preferences_souples`, `niveau_detail`, `coherence_objectif`. Chaque élément : `{valeur, origine, source}` (+ `hypothese` au besoin) |

## `lire_fiche_instrument(ticker)`

`symbole`, `nom`, `classe_actif`, `classe_politique`, `secteur`, `marche`, `devise`, `statistiques_cad` (`volatilite_annualisee`, `pire_baisse`, `temps_sous_l_eau_annees`, `non_recupere`, dates), `premiere_cotation` (actions individuelles : `date`, `recupere_le`), `etiquettes`, `periode`, `seuil_speculatif`, `fiches_generees_le`.

`etiquettes` : `speculatif`, `etablie`, `crypto`, `techno`, `ecarte_esg`. Chacune : `{valeur, regle, declencheur, source}`, avec `valeur` = `true`, `false`, `"indetermine"` ou `"sans_objet"` et `declencheur` = le chiffre ou le statut qui l'a produite.

## `lister_instruments(classe=None)`

`classe` : `liquidites`, `revenu_fixe`, `actions`, `alternatifs`, ou rien pour tout. Renvoie `classe`, `nombre`, `instruments` (liste de `{symbole, nom, classe_politique, classe_actif, secteur, devise, etiquettes, volatilite_annualisee, pire_baisse}`).

## `etat_des_lieux(client)`

Notes du portefeuille actuel, sans ordre : `score`, `dimension_min`, `mesure_min`, `notes`, `dans_la_politique`, `statut` (`dans_la_politique` / `hors_politique`), `portefeuille_pct`, `periode`.

`notes` contient `risque`, `diversification`, `preferences`. Chacune : `{note, mesure_min, mesures}`, où `mesures` détaille chaque mesure avec sa `note` et ses chiffres :

- `risque.mesures` : `ampleur` (`pire_baisse`, `pire_baisse_reference`, `pire_baisse_limite`) et `duree` (`temps_sous_l_eau_annees`, `horizon_annees`, `non_recupere`, `debut`, `fin`). Aussi `volatilite_annualisee` et `etalons`.
- `diversification.mesures` : `classe_liquidites`, `classe_revenu_fixe`, `classe_actions`, `classe_alternatifs`, `crypto`, `plus_grosse_action`, `plus_gros_fonds`, `plus_gros_secteur`. Aussi `poids_par_classe`.
- `preferences.mesures` : une entrée par thème `eviter` ou `rechercher` ; `sans_objet: true` s'il n'y en a aucun ; `signalements` (achat favorable dans un thème recherché).

## `simuler_ordre(client, ticker, sens, pourcentage)`

| Champ | Contenu |
|---|---|
| `ordre` | `{ticker, sens, pourcentage}` |
| `portefeuille_avant_pct`, `portefeuille_apres_pct` | Positions avant et après |
| `contraintes_strictes` | `violee`, `themes_violes`, `detail` (par thème : `statut` = `violee`, `respectee`, `signalee`, `ignoree` ou `non_applicable`, `raison`, `declencheur`, `source`) |
| `avant`, `apres` | Même forme que `etat_des_lieux` : `score`, `dimension_min`, `mesure_min`, `notes` |
| `score`, `dimension_min`, `mesure_min` | Raccourcis vers `apres` |
| `verdict` | `{code, libelle, raison}`, `code` = `compatible`, `en_tension`, `incompatible` |
| `direction` | `{cas, libelle, score_avant, score_apres, revient_dans_la_politique}` ; `cas` = `reste_dans_la_politique`, `fait_sortir_de_la_politique`, `hors_politique_rapproche`, `hors_politique_aggrave` ; `remarque` si une contrainte stricte est violée |
| `contribution_risque_apres` | `{ticker, poids_pct, part_du_risque_pct}` : affiché, non noté |
| `periode` | Période des données, devise CAD |

## `chercher_taille_compatible(client, ticker, sens, pourcentage)`

Plus grande taille, par pas de 0,5 % jusqu'au montant demandé, avec un score de 50 ou plus.

| Champ | Contenu |
|---|---|
| `lancee` | `false` si une contrainte stricte est violée (avec `raison`) |
| `taille_compatible_pct` | La taille, ou `null` |
| `taille_demandee_pct`, `pas_pct` | Rappel |
| `issue` | `compatible_tel_quel`, `compatible_avec_ajustement`, `aucune_taille` |
| `courbe` | Liste de `{taille_pct, score, dimension_min, mesure_min}` |
| `contraintes_strictes` | Comme dans `simuler_ordre` |

## Données

Le moteur lit `data/` ou le dossier de la variable `GLC_DATA_DIR`. `data/prices_daily.csv` n'est pas publié (conditions de Yahoo) : `python data/build_dataset.py` le régénère. Les fiches d'instruments sont en cache dans `reference/fiches_instruments.json` ; `python scripts/construire_fiches.py` les reconstruit (accès réseau pour `firstTradeDate` ; `--sans-reseau` réutilise les dates du cache).
