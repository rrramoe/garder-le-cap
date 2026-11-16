# Les agents de Garder le cap

Une équipe de deux agents Strands sur Amazon Bedrock, et du code autour. **Le code fait tout ce qu'une règle peut faire ; un agent fait seulement ce qui demande du jugement.** Aucun chiffre ne vient d'un agent : chaque verdict, note et piste testée vient d'un appel au moteur. Le partage est net : **le chef de dossier comprend et dirige, l'explorateur cherche.**

## Agent principal : le chef de dossier

- **Mission** : monter le dossier d'analyse de cet ordre pour ce client, de A à Z, diriger la recherche et l'expliquer.
- **Objectif** : que le client comprenne, avec des mots de tous les jours, si l'ordre le garde sur le cap qu'il s'est fixé, pourquoi, et ce qui est possible.
- **Quand il agit** : à chaque analyse.
- **Outils** : `lire_fiche_client`, `lire_fiche_instrument`, `decrire_apport`, `simuler_ordre` (appelés ensemble au premier tour), puis `envoyer_explorateur` et `juger_pistes`.
- **Ce qu'il comprend, lui seul** : le cas des deux côtés. Le client : sa fiche, sa politique, son portefeuille et où il se tient déjà face à ses limites. L'ordre : l'instrument, son profil financier, ce qu'il ajouterait à ce portefeuille. Il en tire la **finalité supposée** de l'ordre (une hypothèse, montrée comme telle dans le rapport) et juge la **cohérence** de l'ordre avec l'objectif, l'horizon et l'expérience déclarés.
- **Ses deux décisions de chef** :
  1. **Le tri** : faut-il chercher, et avec quel mandat (finalité à préserver, cause à traiter, ce que les pistes doivent respecter, pistes à explorer d'abord). Un ordre compatible n'a pas de recherche ; un ordre en tension en a une. Pour un ordre incompatible, il décide s'il envoie un mandat étroit (remplacer l'instrument sans violer la règle stricte) ou rien.
  2. **Le jugement** des pistes testées : répondent-elles à la cause, gardent-elles la finalité, respectent-elles les préférences et l'expérience ? Si le travail est faible, il le renvoie une fois avec une critique précise ; un bon travail n'est pas renvoyé.
- **Ce qu'il rend** : une explication standard, la même pour tout client, en courts paragraphes titrés, dans cet ordre et seulement s'ils s'appliquent : **Le verdict.** (le verdict du moteur et sa direction, reprise telle quelle), **La raison.** (l'angle déterminant et le chiffre de sa mesure face à sa limite), **Ce qui est possible.** (les pistes testées et leur verdict, ou pourquoi personne n'a cherché), **Votre objectif.** (seulement quand l'ordre va clairement contre l'objectif, l'horizon ou l'expérience déclarés), **À savoir.** (l'hypothèse ou la limite qui compte). De 80 à 120 mots ; au-delà de 180, le code le fait réécrire. L'expérience ne change le texte que d'une phrase : pour un débutant, ce qu'est une opération avancée.
- **Comment il parle** : des angles sous lesquels le moteur a évalué l'ordre (ceux qu'il renvoie), jamais d'une note globale ; l'angle dont la note est la plus basse décide du verdict et s'appelle « l'angle déterminant ». Un mot pour une chose : angle, note, note de passage, mesure, limite, cible, verdict, piste testée, analyse. Ni seuil chiffré (« dans votre politique », « à la limite »), ni année, ni date.
- **Ce qu'il ne fait pas** : aucun calcul, aucun verdict ni note à lui, aucune recommandation ; il ne teste aucune piste lui-même.
- **Pourquoi le code seul ne suffit pas** : le code sait qu'une mesure dépasse sa limite ; il ne sait pas ce que ce client cherchait en passant cet ordre, ni si les pistes trouvées le gardent, ni le dire simplement.

## Agent explorateur : le chercheur de pistes, sous mandat

- **Mission** : sous le mandat du chef de dossier, trouver et tester les pistes qui servent la finalité qu'il nomme et répondent à la cause qu'il nomme.
- **Objectif** : deux à quatre pistes testées, chacune avec une phrase qui dit comment elle sert la finalité et répond à la cause ; ou le constat qu'aucune piste raisonnable n'existe sous ce mandat.
- **Quand il agit** : seulement quand le chef de dossier l'envoie, et une seconde fois au plus s'il renvoie le travail.
- **Outils** : `lire_fiche_instrument` et `decrire_apport` (pour un autre instrument), `lister_instruments`, `simuler_ordre`, `simuler_scenario`, `chercher_taille_compatible`. Chaque essai porte sa `raison`.
- **Ce qu'il décide : la recherche elle-même.** Quels candidats (à partir des candidats classés par proximité, leur type, leur industrie, leur dividende, la part déjà détenue d'un fonds), quelles sortes de pistes (un montant plus petit, un autre instrument, un achat partagé avec un fonds, un achat payé par une vente) et quelles combinaisons, comment s'adapter après un résultat, et quand il en sait assez.
- **Ce qu'il ne fait pas** : il ne refait pas la lecture du client et ne forme pas sa propre finalité ; aucun calcul, verdict ou note ; aucune recommandation ; aucune piste qui vide le portefeuille.
- **Ce qu'il rend** au chef de dossier : les pistes retenues (quatre au plus) et un bilan ; pour chaque piste sa sorte, sa raison, le verdict du moteur et son angle déterminant.
- **Pourquoi le code seul ne suffit pas** : une table fixe « cause → piste » proposerait le même fonds à tous ; choisir un candidat qui garde la finalité nommée, écarter ce qu'un client évite, choisir la position à vendre et changer de piste après un résultat, c'est du jugement.

## Pas de troisième agent

Le contrôle des chiffres (code) et le garde-fou Bedrock (refus du conseil personnalisé et des transactions réelles, ancrage contextuel) sont les seuls contrôles. Un agent vérificateur referait avec un modèle ce que ces contrôles font déjà sans modèle.

## Ce que fait le code

- **Le moteur** (`moteur/api.py`) donne chaque note, verdict et direction, et la **cause** du verdict (l'angle déterminant, sa mesure, sa cible, sa limite et sa source). La note de passage est celle du moteur ; aucun agent ne l'écrit.
- **L'envoi de l'explorateur** : refusé pour un ordre compatible ; une fois par analyse. Mandat « remplacer » pour un ordre incompatible : les outils n'acceptent que les pistes qui remplacent l'instrument, et refusent toute piste qui viole une règle stricte, quel que soit le mandat ; le verdict de l'ordre ne change pas. Pour un client débutant, aucune piste sur marge ou à découvert. Les sortes de pistes permises sont dites d'avance à l'explorateur.
- **Le jugement** : « a_completer » relance l'explorateur pour un tour de trois essais au plus, une seule fois (le second renvoi est refusé), et seulement s'il tient dans un budget de 60 s pour toute l'analyse.
- **Les données de recherche** données à l'explorateur avec le mandat : le résultat de l'ordre et sa cause, la fiche du client de façon générique (une réponse ajoutée à la fiche lui arrive sans changer le code), la fiche de l'instrument et son apport. Ses essais lui reviennent sous forme compacte ; les résultats complets vont dans la trace.
- **Les bornes** : six essais au plus, quatre pistes rendues au plus ; dans un scénario, des ventes qui ne dépassent ni le total des achats ni la position détenue ; des limites de tours pour chaque agent ; un délai pour l'explorateur.
- **Les pistes testées** du rapport sont construites à partir des résultats des outils, jamais du texte d'un agent ; leur étiquette vient des ordres et du type des instruments.
- **Les contrôles** de l'explication : chaque chiffre doit venir d'un outil ; le garde-fou Bedrock mesure l'ancrage ; le code refuse une année ou une date, une direction qui contredit celle du moteur, les mots « score », « maillon », « chaîne » ou « dimension », un texte de plus de 180 mots, et le mot « exclu » appliqué à l'expérience. Quand un contrôle signale le texte, le chef de dossier le réécrit une seule fois ; le nouveau texte est vérifié à son tour.
- **Le garde-fou** s'applique à chaque appel du chef de dossier ; pour l'explorateur, à ses phrases montrées dans le rapport (raisons, bilan), son entrée n'étant faite que de faits écrits par le code et du mandat.
- **Le repli** : si l'explorateur échoue ou dépasse son délai, le chef de dossier finit avec la taille compatible calculée par le code (ou sans piste quand aucune n'est permise), et le rapport le dit.
- **La mémoire des analyses** : deux demandes identiques (même fiche, même ordre, mêmes réglages) partagent l'analyse en cours, étapes rejouées ; une analyse finie et réussie est gardée et rejouée avec ses étapes, marquée « analyse déjà faite pour cet ordre » (`memoire` dans le résultat ; `relancer=True` la refait). `scripts/rechauffer_analyses.py` prépare les ordres préremplis des clients enregistrés après un déploiement.
- **Le suivi en direct** : chaque étape est envoyée à l'interface avec le nom de l'agent (`agent/suivi.py`).

## La trace de chaque analyse

Chaque analyse réellement faite (pas un rejeu de la mémoire) laisse une trace dans l'espace AWS privé du projet : un fichier JSON dans le bucket privé, sous `traces/<date UTC>/<identifiant>.json`, et une ligne compacte dans Amazon CloudWatch Logs (groupe `garder-le-cap`, un flux par jour : identifiant, verdict, angle déterminant, durée, modèles, repli). Elle s'écrit en fond, avec des délais courts : une trace qui échoue ne retarde, ne change ni ne casse l'analyse, et le visiteur n'en voit rien. Le résultat de l'analyse porte son identifiant (`trace_aws`), gardé aussi par la mémoire : une analyse rejouée montre l'identifiant de sa trace d'origine.

La trace contient l'identifiant, l'heure UTC, la version de l'application, une empreinte de la fiche et son profil déduit (jamais ses réponses, son nom ni les poids de son portefeuille), l'ordre, les modèles et les réglages, chaque étape dans l'ordre (le tri et le mandat du chef de dossier, chaque appel d'outil de chaque agent avec ses arguments et la réponse du moteur reçue, le retour de l'explorateur, le jugement et le renvoi éventuel), les contrôles de l'explication, le garde-fou, le verdict, la direction et l'angle déterminant donnés par le moteur, l'explication, la durée et le repli éventuel. Elle relie ainsi chaque conclusion de l'explication aux réponses du moteur sur lesquelles elle repose. Aucune adresse de visiteur, aucun identifiant ni secret.

**Réglages** (une variable revient au comportement d'avant) : `GLC_TRACES=0` (pas de trace ; sans bucket configuré, aucune trace), `GLC_MEMOIRE=0` (pas de mémoire), `GLC_CHEF=0` (l'équipe sans tri ni jugement), `GLC_EQUIPE=0` (l'agent seul), `GLC_EFFORT` (chef de dossier, « medium ») et `GLC_EFFORT_EXPLORATEUR` (« low »). **Fichiers** : `agent/prompts/principal_chef.md`, `agent/prompts/explorateur_mandat.md`, `agent/inspection.py`, `agent/explorateur.py`, `agent/outils.py`, `agent/memoire.py`, `agent/traces.py`.
