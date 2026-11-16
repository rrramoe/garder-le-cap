# Les agents de Garder le cap

Une équipe de deux agents Strands sur Amazon Bedrock, et du code autour. **Le code fait tout ce qu'une règle peut faire ; un agent fait seulement ce qui demande du jugement.** Aucun chiffre ne vient d'un agent : chaque verdict, note et piste vient d'un appel au moteur. Le partage est net : **le chef de dossier comprend et dirige, l'explorateur cherche.**

## Agent principal : le chef de dossier

- **Mission** : monter le dossier d'analyse de cet ordre pour ce client, de A à Z, l'expliquer, et diriger la recherche.
- **Objectif** : que le client comprenne, avec ses mots, si l'ordre le garde sur le cap qu'il s'est fixé, pourquoi, et ce qui est possible.
- **Quand il agit** : à chaque analyse.
- **Outils** : `lire_fiche_client`, `lire_fiche_instrument`, `decrire_apport`, `simuler_ordre`, `envoyer_explorateur`, `juger_pistes`.
- **Ce qu'il comprend, lui seul** : le cas des deux côtés. Le client : sa fiche, sa politique, son portefeuille et où il se tient déjà face à ses limites. L'ordre : l'instrument, son profil financier, ce qu'il ajouterait à ce portefeuille. Il en tire la **finalité supposée** de l'ordre (une hypothèse, montrée comme telle dans le rapport) et juge la **cohérence** de l'ordre avec l'objectif, l'horizon et l'expérience déclarés.
- **Ses deux décisions de chef** : 1. **le tri** : faut-il chercher, et avec quel mandat (finalité à préserver, cause à traiter, ce que les pistes doivent respecter, pistes à explorer d'abord) ; pour un ordre incompatible, un mandat étroit, remplacer l'instrument sans violer la règle, ou ne rien chercher s'il juge que rien ne peut servir le même but. 2. **le jugement** des pistes : répondent-elles à la cause, gardent-elles la finalité, respectent-elles les préférences et l'expérience ? Si le travail est faible, il le renvoie une fois avec une critique précise ; un bon travail n'est pas renvoyé.
- **Comment il parle** : des angles sous lesquels le moteur a évalué l'ordre (ceux qu'il renvoie), jamais d'une note globale ; l'angle dont la note est la plus basse décide du verdict et s'appelle « l'angle déterminant ». Un mot pour une chose : angle, note, note de passage, mesure, limite, cible, verdict, piste testée, analyse ; le code fait réécrire un texte qui dit « score », « maillon », « chaîne » ou « dimension ».
- **Ce qu'il ne fait pas** : aucun calcul, aucun verdict ni note à lui, aucune recommandation ; il ne teste aucune piste lui-même.
- **Ce qu'il rend** : l'explication en quatre parties (Verdict, Pourquoi, Ce qui est possible, Hypothèses et limites), 180 mots au plus.
- **Pourquoi le code seul ne suffit pas** : le code sait qu'une mesure dépasse sa limite ; il ne sait pas ce que ce client cherchait en passant cet ordre, ni si les pistes trouvées le gardent, ni le dire avec les mots d'un débutant.

## Agent explorateur : le chercheur de pistes, sous mandat

- **Mission** : sous le mandat du chef de dossier, trouver et tester les pistes qui servent la finalité qu'il nomme et répondent à la cause qu'il nomme.
- **Objectif** : deux à quatre pistes testées, chacune avec une phrase qui dit comment elle sert la finalité et répond à la cause ; ou le constat qu'aucune piste raisonnable n'existe sous ce mandat.
- **Quand il agit** : seulement quand le chef de dossier l'envoie (ordre en tension, ou incompatible avec un mandat étroit), et une seconde fois au plus s'il renvoie le travail.
- **Outils** : `lire_fiche_instrument`, `decrire_apport` (pour un autre instrument), `lister_instruments`, `simuler_ordre`, `simuler_scenario`, `chercher_taille_compatible`. Chaque essai porte sa `raison`.
- **Ce qu'il décide : la recherche elle-même.** Quels candidats (à partir des candidats classés par proximité, leur type, leur industrie, leur dividende, la part déjà détenue d'un fonds), quelles familles de pistes et quelles combinaisons (un montant plus petit plus un complément, une partie payée par une vente), comment s'adapter après un résultat, et quand il en sait assez.
- **Ce qu'il ne fait pas** : il ne refait pas la lecture du client et ne forme pas sa propre finalité ; aucun calcul, verdict ou note ; aucune recommandation ; aucune piste qui vide le portefeuille.
- **Ce qu'il rend** au chef de dossier : les pistes retenues (quatre au plus) et un bilan ; pour chaque piste sa famille, sa raison et le résultat du moteur.
- **Pourquoi le code seul ne suffit pas** : une table fixe « cause → piste » proposerait le même fonds à tous ; choisir un candidat qui garde la finalité nommée, écarter ce qu'un client évite, choisir la position à vendre et changer de piste après un résultat, c'est du jugement.

## Pas de troisième agent

Le contrôle des chiffres (code) et le garde-fou Bedrock (refus du conseil et des transactions réelles, ancrage contextuel) sont les seuls contrôles. Un agent vérificateur referait avec un modèle ce que ces contrôles font déjà sans modèle.

## Ce que fait le code

- Les trois premières lectures et la simulation de l'ordre passent par le moteur (`moteur/api.py`) ; chaque note, verdict et direction en vient.
- La **cause** du verdict (`cause` dans le résultat de la simulation) : la mesure qui décide et ce qui la fait, lue dans les notes déjà calculées.
- L'**envoi de l'explorateur** : refusé pour un ordre compatible ; une seule fois par analyse. Pour un ordre incompatible, mandat « remplacer » : les outils n'acceptent que les pistes qui remplacent l'instrument (seules, ou payées par une vente), et refusent toute piste qui viole une règle stricte, quel que soit le mandat. Le verdict de l'ordre ne change pas.
- Le **jugement** : `juger_pistes` après le retour de l'explorateur ; « a_completer » relance l'explorateur pour un tour de trois essais au plus, une seule fois (le code refuse le second renvoi).
- L'**expérience ne baisse jamais un verdict** : le verdict vient des notes mesurées sur le portefeuille ; les `points_attention` (opération avancée et son risque, profil déclaré, limites) sont des faits pour les agents et le rapport. Pour un client débutant, les outils de l'explorateur refusent toute piste sur marge ou à découvert.
- Les **données de recherche** données à l'explorateur avec le mandat, comme matériau pour ses outils : le résultat de l'ordre et sa cause, la fiche du client de façon générique (chaque réponse, la politique déduite, le portefeuille), la fiche de l'instrument et son apport (`decrire_apport`, candidats classés par proximité). Pendant ses essais, l'explorateur reçoit des résultats compacts (verdict, score, direction, cause) ; les résultats complets vont dans la trace et le rapport.
- La **vitesse** : chaque agent fait ses appels indépendants dans un même tour ; les agents raisonnent à l'effort « medium » (`GLC_EFFORT=high` revient au défaut du modèle).
- Les **bornes** : six essais au plus (l'outil refuse le septième), quatre pistes rendues au plus (les dernières testées si l'explorateur n'en désigne pas) ; dans un scénario, des ventes qui ne dépassent jamais le total des achats ni la position détenue ; une limite de tours pour chaque agent (10 pour le chef de dossier, 8 pour l'explorateur par tour) ; un délai de 150 s pour l'explorateur.
- La liste **`pistes`** du rapport, construite à partir des résultats des outils, jamais du texte d'un agent.
- Le **garde-fou de l'explorateur** : son entrée n'est faite que de faits écrits par le code et du mandat du chef de dossier ; le garde-fou Bedrock s'applique à ses phrases montrées dans le rapport (raisons, bilan), qui sont retirées s'il intervient. Le chef de dossier garde le garde-fou sur chaque appel.
- Les **contrôles** de l'explication : chaque chiffre doit venir d'un outil, puis le garde-fou Bedrock mesure l'ancrage.
- La **correction** : quand un contrôle signale le texte (un chiffre absent des outils, un passage non appuyé, plus de 180 mots), le code renvoie la liste des problèmes au chef de dossier, qui réécrit une seule fois ; le nouveau texte est vérifié à son tour, et l'avis reste si le problème demeure (`correction` dans le résultat).
- Le **repli** : si l'explorateur échoue ou dépasse son délai, le chef de dossier finit seul avec la taille compatible calculée par le code, et le rapport le dit.
- Le **suivi en direct** : chaque étape est envoyée à l'interface avec le nom de l'agent (`agent/suivi.py`).

Réglages : `GLC_CHEF=0` revient à l'équipe d'avant (envoi pour un ordre en tension seulement, sans jugement, `agent/prompts/principal.md` et `agent/prompts/explorateur.md`) ; `GLC_EQUIPE=0` revient à l'agent seul (`agent/prompts/systeme.md`). Fichiers : `agent/prompts/principal_chef.md`, `agent/prompts/explorateur_mandat.md`, `agent/inspection.py`, `agent/explorateur.py`, `agent/outils.py`.
