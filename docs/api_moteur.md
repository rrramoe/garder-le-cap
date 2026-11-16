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
- **Sens** : `"achat"` ou `"vente"`. **Pourcentage** : en % du portefeuille (15 = 15 %). Un achat est payé par l'encaisse (`ZST.TO`), une vente y est versée.
- **Opération** (argument facultatif `operation`, voir plus bas) : `"comptant"` par défaut, `"marge"` ou `"decouvert"`. Au comptant, un achat plus gros que l'encaisse ou une vente plus grosse que la position renvoie une erreur.
- Les notes vont de 0 à 100 (100 = sur la cible, 70 = limite de la politique, la note de passage `NOTE_DE_PASSAGE`, portée par chaque résultat dans `note_de_passage`). Les pires baisses sont des fractions négatives (−0,18 = −18 %). Les poids sont en %.
- Les réponses possibles au questionnaire sont dans `reference/questionnaire.json` (`objectif`, `horizon`, `fluctuations`, `capacite_perte`, `besoin_liquidite`, `experience`, et l'échelle des thèmes `exclure / eviter / neutre / rechercher / obligatoire`). Les thèmes sont dans `reference/themes.json` : une ligne par thème (`id`, `libelle`, `etiquette`) ; ajouter un thème, c'est ajouter une ligne et l'étiquette du même nom dans les fiches d'instruments (`scripts/construire_fiches.py`). Huit thèmes : les cinq de départ, plus `dividende`, `devise_etrangere` et `action_individuelle`. Un thème sans réponse vaut `neutre`.

## `lire_fiche_client(client)`

| Champ | Contenu |
|---|---|
| `id`, `nom` | Identifiant et nom |
| `questionnaire` | Les réponses : `objectif`, `horizon`, `fluctuations`, `capacite_perte`, `besoin_liquidite`, `experience`, `themes` (8 thèmes) |
| `portefeuille_pct` | Positions, ticker → % |
| `poids_par_classe_pct` | `liquidites`, `revenu_fixe`, `actions`, `alternatifs` |
| `deduit` | `profil`, `fourchettes_pct`, `besoin_liquidite_pct`, `horizon_annees`, `plafonds_concentration_pct`, `crypto_pct`, `contraintes_strictes`, `preferences_souples`, `niveau_detail`, `coherence_objectif`. Chaque élément : `{valeur, origine, source}` (+ `regle`, `hypothese` au besoin) |

**Capacité à supporter une perte** (`capacite_perte`). Même échelle que `fluctuations` (`faibles` … `elevees`), chaque niveau décrit par une situation. Le profil retenu est le plus prudent des deux : ce que le client accepte (`fluctuations`) et ce que sa situation permet (`capacite_perte`). Tout ce qui suit le profil suit le profil retenu : fourchettes et cibles, portefeuilles étalons de la note de risque, plafond des cryptoactifs, cohérence avec l'objectif. `deduit.profil` ajoute `accepte`, `permis` (`{valeur, libelle}`), `decide_par` (`fluctuations`, `capacite` ou `les_deux`) et `phrase`. Sans réponse, `capacite_perte` prend la valeur de `fluctuations` : rien ne change. Règle : `acvm_capacite_perte` ; formulation des situations : `hypothese_capacite_libelles`.

**Besoin de liquidités dans les 12 prochains mois** (`besoin_liquidite` : `aucun`, `jusqu_10`, `10_25`, `25_40`). La borne haute de la tranche (0, 10, 25 ou 40 %) est le besoin ; la famille `liquidite` le compare aux liquidités après l'ordre (voir « Modèle de notation en cinq familles »). Les fourchettes de la diversification restent celles du profil. `deduit.besoin_liquidite_pct` : `{valeur, origine, phrase, source}`, par exemple « Vous gardez au moins 10 % en liquidités pour vos besoins de l'année. ». Sans réponse : `aucun`, la famille est sans objet. Règle : `hypothese_besoin_liquidite`.

## `lire_fiche_instrument(ticker, montant_cad=None)`

`symbole`, `identifiant_univers`, `nom`, `classe_actif`, `classe_politique`, `secteur`, `marche`, `devise`, `statistiques_cad` (`volatilite_annualisee`, `pire_baisse`, `temps_sous_l_eau_annees`, `non_recupere`, dates), `premiere_cotation` (actions individuelles : `date`, `recupere_le`), `etiquettes`, `faits_marche`, `periode`, `seuil_speculatif`, `fiches_generees_le`.

`faits_marche` : des faits sur le passé, calculés par `scripts/construire_fiches.py` (module `moteur/faits_marche.py`) sur les fichiers des organisateurs ; aucun n'entre dans un score. En CAD sur le calendrier du moteur, sauf mention. Une donnée absente ou trop courte vaut `"indetermine"`.

| Bloc | Contenu |
|---|---|
| `performance` | `rendement_total`, `par_annee` (année → rendement), `annees_partielles`, `meilleure_annee` et `pire_annee` (années complètes), `annee_difficile_du_marche` (`{annee, marche: XIU.TO, rendement_marche, rendement}`), `ecart_au_plus_haut`, `date_plus_haut` |
| `risque` | `volatilite_baissiere` (annualisée), `pire_jour`, `pire_mois`, `baisses_de_plus_de_20_pct` (épisodes) |
| `marches` | `actions_canada` (XIU.TO), `actions_etats_unis` (SPY), `obligations_canada` (XBB.TO) : `{beta, correlation}` ; `part_volatilite_due_au_change` (titres en USD : 1 - variance en USD / variance en CAD ; `sans_objet` sinon) |
| `revenu` | Devise de cotation : `dividendes_12_mois` (par action), `rendement_dividende` (sur le dernier cours), `annees_avec_dividende`, `dividende_en_hausse` (dernière année complète contre la première), `dividende_par_annee`, `fractionnements` |
| `liquidite` | `valeur_echangee_moyenne_par_jour` (devise de cotation) et `_cad`, sur les 63 dernières séances ; avec `montant_cad` : `montant_ordre_cad` et `jours_de_volume_ordre` (montant / valeur échangée moyenne) |
| `taux` | `correlation_avec_taux_10_ans` (rendements hebdomadaires contre variation hebdomadaire du taux 10 ans de la devise : `BD.CDN.10YR.DQ.YLD` ou `DGS10`) |

Sources : `donnees_marche`, `donnees_dividendes`, `donnees_taux`, conventions `hypothese_faits_marche`.

`profil` (hors des données des organisateurs) : lu dans `reference/profils_instruments.json`, construit par `python scripts/profils_instruments.py` (Yahoo Finance via yfinance ; le téléchargement brut va dans `data/profils_bruts/`, les deux sont ignorés par git ; `python scripts/creer_bucket.py` dépose le profil dans le bucket privé). Entreprise : `{type: "entreprise", description, industrie, pays, devise_capitalisation, devise_des_etats_financiers, capitalisation, chiffre_affaires, benefice_net, dette, encaisse, flux_tresorerie_signes: {exploitation, investissement, financement}, exercice_flux}`. Fonds : `{type: "fonds", description, famille, dix_plus_grandes_positions: [{symbole, nom, poids}], secteurs, types_actifs, ratio_frais_pct, actif_total}`. Cryptoactif : `{type: "cryptoactif", description}`. Chaque profil porte `recupere_le` et `source: "yfinance_profils"`. La `description` est une phrase composée par le projet à partir des champs, pas le texte de Yahoo. Absent : `"indetermine"`. `data/corporate_actions.csv` et `data/macro_rates.csv` ne sont pas publiés dans le dépôt : copiez-les depuis le dossier des organisateurs (ou régénérez-les avec `python data/build_dataset.py`), puis `python scripts/construire_fiches.py --sans-reseau`.

`etiquettes` : `speculatif`, `etablie`, `crypto`, `techno`, `ecarte_esg`, `dividende` (au moins un dividende dans les 12 derniers mois des données, `corporate_actions.csv`), `devise_etrangere` (cotée dans une autre devise que le CAD), `action_individuelle` (action d'une seule entreprise, par opposition à un fonds ou à un cryptoactif). Chacune : `{valeur, regle, declencheur, source}`, avec `valeur` = `true`, `false`, `"indetermine"` ou `"sans_objet"` et `declencheur` = le chiffre ou le statut qui l'a produite.

## `lister_instruments(classe=None)`

`classe` : `liquidites`, `revenu_fixe`, `actions`, `alternatifs`, ou rien pour tout. Renvoie `classe`, `nombre`, `instruments` (liste de `{symbole, nom, classe_politique, classe_actif, secteur, devise, etiquettes, volatilite_annualisee, pire_baisse}`).

## Modèle de notation en cinq familles

Les contraintes strictes d'abord ; puis chaque famille prend sa mesure la plus faible ; le verdict suit la famille la plus faible (« une chaîne n'est qu'aussi solide que son maillon le plus faible »). Échelle commune : 100 sur la cible, 70 exactement à la limite (note de passage, fixée en un seul endroit : `notation.NOTE_DE_PASSAGE`, aussi `api.NOTE_DE_PASSAGE`), 0 au double de la distance, une droite de chaque côté de la limite : la même distance coûte 30 points dans la politique et 70 au-delà. Les formules des mesures donnent une note brute (limite à 50, `notation.note_lineaire`, `note_classe`…) que `notation.convertir` porte sur cette échelle ; la conversion est croissante et envoie la limite sur la limite, donc aucun verdict, direction ou taille compatible ne change (`tests/test_note_de_passage.py`). « Compatible » quand la note la plus faible vaut 70 ou plus. Une mesure ou une famille qui ne peut pas être calculée vaut `note: null` avec `statut` (`indetermine` ou `sans_objet`) et ne décide pas. Le champ `score` reste la note la plus faible ; l'interface ne l'affiche pas comme un chiffre global.

`notes` : une entrée par famille, dans l'ordre de `familles`, chacune `{note, mesure_min, mesures, question}` (+ `sans_objet`). Chaque mesure porte `note`, `libelle`, et selon le cas `valeur`, `cible`, `limite`, `unite`, `phrase`, `source`, `hypothese`. Une famille ou une mesure ajoutée apparaît sans changement côté agents ou interface.

| Famille (`question`) | Mesures |
|---|---|
| `objectif` (« L'ordre sert-il mon objectif ? ») | Une seule, selon l'objectif : `capital_preserve` (pire rendement cumulé sur une fenêtre de la durée de l'horizon, de 1 à 3 ans ; limite 0 %, 100 à +pire année publiée du profil, 0 à -pire année), `revenu` (rendement en revenu du portefeuille sur 12 mois ; cible = celui de l'étalon de référence du profil, limite = celui de l'étalon le plus audacieux, ou la moitié de la cible s'il n'est pas plus bas), `actions` (poids des actions : formule de classe pour « croissance équilibrée », côté bas seulement pour « croissance à long terme »). Hypothèse `hypothese_objectif` |
| `risque` (« Le risque reste-t-il dans ce que j'accepte ? ») | `ampleur`, `duree` (inchangées) ; `fluctuations` : écart-type annualisé des rendements mensuels, cible = borne basse, limite = borne haute du niveau des régulateurs associé au profil (Revenu faible 0-6, Conservateur faible à moyen 6-11, Équilibré moyen 11-16, Croissance moyen à élevé 16-20, Croissance maximale élevé ≥ 20 : `sans_objet`, pas de plafond publié ; source `acvm_81_102_annexe_f`) ; `pire_annee` : pire rendement sur 252 séances, cible 0 %, limite = pire année publiée par la banque (`fbngp_pire_annee_2024`) |
| `liquidite` (« Mon argent reste-t-il disponible ? ») | `liquidites_besoin` : liquidités après l'ordre, limite = le besoin déclaré, cible = besoin + cible de liquidités du profil ; famille `sans_objet` sans besoin. La fourchette des liquidités de la diversification reste celle du profil |
| `diversification` (« Mon portefeuille reste-t-il bien réparti ? ») | Les cinq mesures d'avant ; `geographie_actions` : en % du portefeuille, actions canadiennes face à cible d'actions du profil x 40 % et actions hors du Canada face à x 60 % (`fbngp_repartition_actions_2024` : 40 % Canada, 40 % États-Unis, 20 % étranger), limites à 10 points de part et d'autre de chaque cible (`rbcgam_fourchettes_regionales_2025`) ; la plus faible des deux (`decide`, `sous_mesures`) ; hypothèse `hypothese_geographie` |
| `preferences` (« L'ordre respecte-t-il mes préférences ? ») | Inchangée, tous les thèmes de la fiche |

Limites publiées et bandes : `reference/limites_risque.json`. La solidité recalcule seulement la pire baisse et la durée sur ses deux fenêtres ; les autres familles y gardent leur note de la période complète.

## `etat_des_lieux(client)`

Notes du portefeuille actuel, sans ordre : `score`, `dimension_min`, `mesure_min`, `notes`, `dans_la_politique`, `statut` (`dans_la_politique` / `hors_politique`), `portefeuille_pct`, `periode`.

`notes` contient `risque`, `diversification`, `preferences`. Chacune : `{note, mesure_min, mesures}`, où `mesures` détaille chaque mesure avec sa `note` et ses chiffres :

- `risque.mesures` : `ampleur` (`pire_baisse`, `pire_baisse_reference`, `pire_baisse_limite`) et `duree` (`temps_sous_l_eau_annees`, `horizon_annees`, `non_recupere`, `debut`, `fin`). Aussi `volatilite_annualisee` et `etalons`.
- `diversification.mesures` : `classe_liquidites`, `classe_revenu_fixe`, `classe_actions`, `classe_alternatifs`, `crypto`, `plus_grosse_action`, `plus_gros_fonds`, `plus_gros_secteur`. Aussi `poids_par_classe`.
- `preferences.mesures` : une entrée par thème `eviter` ou `rechercher` ; `sans_objet: true` s'il n'y en a aucun ; `signalements` (achat favorable dans un thème recherché).

## `simuler_ordre(client, ticker, sens, pourcentage, operation="comptant")`

| Champ | Contenu |
|---|---|
| `ordre` | `{ticker, sens, pourcentage, operation}` |
| `portefeuille_avant_pct`, `portefeuille_apres_pct` | Positions avant et après |
| `contraintes_strictes` | `violee`, `themes_violes`, `detail` (par thème : `statut` = `violee`, `respectee`, `signalee`, `ignoree` ou `non_applicable`, `raison`, `declencheur`, `source`) |
| `avant`, `apres` | Même forme que `etat_des_lieux` : `score`, `dimension_min`, `mesure_min`, `notes` |
| `score`, `dimension_min`, `mesure_min` | Raccourcis vers `apres` |
| `verdict` | `{code, libelle, raison}`, `code` = `compatible`, `en_tension`, `incompatible` |
| `direction` | `{cas, libelle, score_avant, score_apres, revient_dans_la_politique}` ; `cas` = `reste_dans_la_politique`, `fait_sortir_de_la_politique`, `hors_politique_rapproche`, `hors_politique_aggrave` ; `remarque` si une contrainte stricte est violée |
| `contribution_risque_apres` | `{ticker, poids_pct, part_du_risque_pct}` : affiché, non noté |
| `operation` | `{code, libelle, levier_avant, levier_apres, exposition_brute_apres_pct, exposition_empruntee_apres_pct, hypotheses, limites, controle_experience}` (voir plus bas) |
| `solidite` | Voir `solidite` ci-dessous : le score après l'ordre sur 2022 seule et sur la période sans 2022 |
| `cause` | Ce qui décide du verdict, lu dans les notes déjà calculées (voir `cause` ci-dessous) |
| `points_attention` | Des faits, sans note : `{type, texte}` avec `type` = `operation` (opération avancée, son risque et le levier après l'ordre), `profil_declare` (expérience, objectif et horizon déclarés, avec leurs codes) et `limite` (les limites déjà dites dans `operation.limites`). Aussi dans `simuler_scenario`. |
| `periode` | Période des données, devise CAD |

### `cause`

Ce qui décide du verdict, sans aucune note nouvelle : `dimension`, `mesure`, `note` (le score), `sous_le_seuil`, `porte_par_l_ordre` (un instrument de l'ordre est-il en cause ?), `autres_mesures_sous_le_seuil` (`{dimension, mesure, note}`), et selon `type` :

| `type` | Ce qui fait la mesure |
|---|---|
| `contrainte_stricte` | `themes_violes` : le verdict vient d'elles seules |
| `risque` | `valeur` et `limite` (pire baisse et sa limite, plus `reference` ; ou durée sous l'eau et horizon), `part_du_risque_pct` des instruments de l'ordre |
| `classe` | `classe`, `poids`, `min`, `cible`, `max`, `cote` (`au_dessus` ou `en_dessous`), `classes_des_ordres` |
| `plafond` | `poids`, `plafond`, et `instrument` (plus grosse action, plus gros fonds) ou `secteur` ; rien de plus pour `crypto` |
| `preference` | `theme`, `reponse`, `poids_expose`, `instruments` exposés |

## `simuler_scenario(client, ordres)`

Plusieurs ordres (1 à 4) appliqués ensemble : `ordres` est une liste de `{ticker, sens, pourcentage}` (+ `operation`). Les ventes passent d'abord et sont versées à l'encaisse ; les achats sont payés par l'encaisse. Un achat plus gros que l'encaisse plus les ventes renvoie l'erreur habituelle ; le total des ventes ne peut pas dépasser celui des achats (une vente sert seulement à payer un achat) ; un même instrument ne figure qu'une fois.

Même résultat que `simuler_ordre`, plus `ordres` ; `ordre` est le premier ordre. Les contraintes strictes sont vérifiées pour chaque ordre (`detail` porte le `ticker`). Les formules sont celles de `simuler_ordre` ; la note de préférences dépend de l'ordre (thème recherché vendu, opération) : elle est calculée avec chaque ordre et la plus basse évaluation est gardée. Un scénario d'un seul ordre donne exactement `simuler_ordre`.

## `solidite(client, ticker, sens, pourcentage)`

Section 7.7 : la note de risque du portefeuille après l'ordre est recalculée sur deux fenêtres, **défavorable** (2022 seule) et **favorable** (toute la période sans 2022), avec les mêmes formules et des portefeuilles étalons recalculés sur la même fenêtre. Le score d'une fenêtre est le minimum de cette note de risque et des notes de diversification et de préférences (qui ne dépendent pas de l'historique). Le score principal reste celui de la période complète.

| Champ | Contenu |
|---|---|
| `statut`, `libelle` | `solide` (la note la plus faible est du même côté de 70 dans les deux fenêtres) ou `fragile` |
| `explication`, `regle` | La règle et son résultat, en français |
| `score_principal` | Le score de la période complète |
| `fenetres` | `defavorable` et `favorable` : `{libelle, debut, fin, score, dimension_min, dans_la_politique, note_risque}` ; `note_risque` = `{note, mesure_min, mesures}` (`ampleur`, `duree`) |
| `ordre`, `verdict` | Rappel de l'ordre et du verdict |

Le même bloc figure dans le résultat de `simuler_ordre` (champ `solidite`). Fenêtre favorable : les rendements d'avant et d'après 2022 sont mis bout à bout, les dates d'après 2022 avancées de 365 jours (la durée sous l'eau ne compte pas l'année retirée).

## `chercher_taille_compatible(client, ticker, sens, pourcentage, operation="comptant")`

Plus grande taille, par pas de 0,5 % jusqu'au montant demandé, dont la note la plus faible atteint la note de passage (70). Pour la marge ou le découvert, chaque point de la courbe porte aussi son `levier`, et le résultat rappelle `operation`.

| Champ | Contenu |
|---|---|
| `lancee` | `false` si une contrainte stricte est violée (avec `raison`) |
| `taille_compatible_pct` | La taille, ou `null` |
| `taille_demandee_pct`, `pas_pct` | Rappel |
| `issue` | `compatible_tel_quel`, `compatible_avec_ajustement`, `aucune_taille` |
| `courbe` | Liste de `{taille_pct, score, dimension_min, mesure_min}` |
| `contraintes_strictes` | Comme dans `simuler_ordre` |

## `decrire_apport(client, ticker, pourcentage=None)`

Ce que l'instrument apporterait au portefeuille du client : **des faits seulement**, sans note ni verdict, pour comprendre un ordre et choisir un complément ou un substitut sur preuves. Mêmes conventions que les autres mesures : rendements quotidiens en CAD (jours sans cotation comptés à 0), même calendrier et même période, portefeuille à poids constants rééquilibré chaque jour. Outil de l'agent : `decrire_apport`, créé par `agent.outils.creer_outil_decrire_apport(client)` (hors de la liste de `creer_outils`).

| Champ | Contenu |
|---|---|
| `ticker`, `nom`, `classe_politique`, `secteur`, `etiquettes_vraies` | L'instrument |
| `correlation_portefeuille` | `{valeur, deja_detenu_pct, libelle, periode}` : corrélation des rendements quotidiens de l'instrument avec ceux du portefeuille actuel |
| `positions_proches` | Les trois positions actuelles les plus corrélées à l'instrument : `{ticker, nom, poids_pct, correlation}` |
| `exposition_actuelle` | `classe` : `{classe, poids_pct, min_pct, cible_pct, max_pct}` ; `secteur` (action individuelle) : `{secteur, poids_pct, positions, plafond_pct, plafond_action_individuelle_pct}`, sinon `null` ; `fonds` (fonds négocié en bourse) : `{poids_actuel_pct, plafond_pct}` ; `etiquettes` : pour chaque étiquette vraie de l'instrument, `{poids_pct, positions, reponse_client, plafond_pct}` (`plafond_pct` pour la crypto seulement) ; `periode` |
| `apres_ordre` | Si `pourcentage` est donné : achat au comptant, `{pourcentage_ordre, poids_pct, part_du_risque_pct, poids_avant_pct, part_du_risque_avant_pct}` (même calcul que `contribution_risque_apres`) ; `{pourcentage_ordre, erreur}` si l'achat est impossible (encaisse insuffisante) ; `null` sans `pourcentage` |
| `candidats` | Les instruments de la même classe, du plus corrélé au moins corrélé à l'instrument : `{symbole, nom, secteur, correlation_avec_instrument, correlation_avec_portefeuille, volatilite_annualisee, pire_baisse, etiquettes, deja_detenu_pct, type, rendement_dividende}` (`type` : `action`, `fonds` ou `crypto`), plus `industrie` pour une action et `positions_deja_detenues` pour un fonds (`{part_du_fonds, titres: [{symbole, poids_dans_le_fonds, poids_chez_le_client_pct}]}` : parmi ses dix plus grandes positions, celles que le client détient déjà) |
| `periode`, `frequence` | Période des données (CAD) ; `quotidienne` |

Instrument inconnu, client inconnu, montant invalide ou historique de prix manquant : `{"erreur": "..."}`.

## Achat sur marge, vente à découvert et expérience

| `operation` | Sens | Effet sur le portefeuille |
|---|---|---|
| `comptant` (défaut) | achat ou vente | Comportement d'origine, inchangé. |
| `marge` | achat | L'achat peut dépasser l'encaisse : `ZST.TO` devient négatif, c'est un emprunt. |
| `decouvert` | vente | La vente peut dépasser la position : le poids devient négatif, le produit va à l'encaisse. |

Une autre combinaison renvoie une erreur (`marge` avec `vente`, `decouvert` avec `achat`, opération inconnue).

**Conventions (hypothèses du projet, dans `sources`)** : `hypothese_marge`, `hypothese_decouvert`, `hypothese_levier`, `hypothese_experience_operations`.

- Le rendement du portefeuille reste la somme pondérée des rendements, poids négatifs compris. Si une journée fait tout perdre, la valeur reste à 0.
- L'emprunt compte comme des liquidités négatives dans la fourchette de liquidités du profil (les poids par classe restent nets).
- Concentration (crypto, plus grosse action, plus gros fonds, plus gros secteur) et thèmes évités : chaque exposition compte en valeur absolue. Une encaisse négative n'est pas une position dans le fonds de liquidités.
- **Levier** = exposition brute (somme des poids en valeur absolue, emprunt exclu) / valeur nette. Il vaut 1 sans marge ni découvert. Affiché, non noté.
- **Limites**, dans `operation.limites` : le coût de l'emprunt au-delà du rendement des liquidités est ignoré ; la perte d'une vente à découvert n'a pas de plafond et l'historique montre seulement ce qui s'est produit ; ni appel de marge ni frais d'emprunt de titres ne sont simulés.

**L'expérience : un repère, pas une pénalité.** L'outil ne baisse jamais un verdict seulement parce que le client débute : le verdict d'un achat sur marge ou d'une vente à découvert vient de ce que le moteur mesure sur le portefeuille après l'ordre (notes de risque avec le levier ou le poids négatif, plafonds en exposition absolue), comme pour tout ordre. L'expérience, l'objectif et l'horizon déclarés arrivent dans `points_attention` et guident la lecture des agents.

Le mécanisme reste dans `reference/operations_experience.json` (hypothèse du projet) : pour chaque opération avancée et chaque expérience, un niveau de l'échelle des thèmes, modifiable sans toucher au code. **Valeur actuelle : `neutre` pour les trois expériences et les deux opérations.** Les autres niveaux, s'ils étaient choisis :

| Niveau | Effet |
|---|---|
| `exclure` | Contrainte stricte : entrée `achat_sur_marge` ou `vente_a_decouvert` dans `contraintes_strictes` (avec `controle: "experience_operation"`), verdict « incompatible », aucune taille cherchée. |
| `eviter` | Préférence souple : mesure `achat_sur_marge` ou `vente_a_decouvert` dans `notes.preferences`, notée `max(0, 100 - 50 * e / 15)` en note brute (puis portée sur l'échelle à 70), où `e` est le poids détenu à découvert ou acheté avec de l'argent emprunté après l'ordre. |
| `neutre` | Aucun effet (valeur actuelle). |

`operation.controle_experience` résume le contrôle : `{id, experience, niveau, effet, raison, source}`, avec `effet` = `contrainte_stricte`, `preference_souple` (plus `note` et `poids_expose`) ou `aucun`.

## Données

Le moteur lit `data/` ou le dossier de la variable `GLC_DATA_DIR`. `data/prices_daily.csv` n'est pas publié (conditions de Yahoo) : `python data/build_dataset.py` le régénère. Les fiches d'instruments sont en cache dans `reference/fiches_instruments.json` ; `python scripts/construire_fiches.py` les reconstruit (accès réseau pour `firstTradeDate` ; `--sans-reseau` réutilise les dates du cache).

## `origine_references()`

D'où les fichiers de référence ont été lus : `lieu` (`s3`, `local` ou `mixte`), `bucket_configure`, `fichiers` (par fichier : `lieu`, et `identique_au_local` pour une lecture S3, ou `repli` et `raison` si S3 n'a pas répondu) et `message`, une phrase en français pour la partie 8 du rapport.

Quand la variable `GLC_BUCKET` est configurée (fichier local `glc.env`, ignoré par git ; voir `glc.env.exemple`), les fichiers de référence, fiches d'instruments comprises, sont lus dans ce bucket S3 privé, sous `reference/` ; sinon dans le dossier `reference/`. Si S3 ne répond pas, le fichier local est lu et le message le dit. `python scripts/creer_bucket.py` crée le bucket (accès public bloqué, chiffrement par défaut, accès hors TLS refusé) et y dépose les fichiers.
