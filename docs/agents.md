# Les agents de Garder le cap

Une équipe de deux agents Strands sur Amazon Bedrock, et du code autour. **Le code fait tout ce qu'une règle peut faire ; un agent fait seulement ce qui demande du jugement.** Aucun chiffre ne vient d'un agent : chaque verdict, score et piste vient d'un appel au moteur.

## Agent principal : le chef de dossier

- **Mission** : monter le dossier d'analyse de cet ordre pour ce client, de A à Z, et l'expliquer.
- **Objectif** : que le client comprenne, avec ses mots, si l'ordre le garde sur le cap qu'il s'est fixé, pourquoi, et ce qui est possible.
- **Quand il agit** : à chaque analyse.
- **Outils** : `lire_fiche_client`, `lire_fiche_instrument`, `simuler_ordre`, `envoyer_explorateur`.
- **Ce qu'il décide** : quelle règle du client et quel objectif déclaré sont en jeu pour cet ordre, y compris un paradoxe (des notes qui montent alors qu'une contrainte stricte est violée, une étiquette indéterminée) ; la mission qu'il confie à l'explorateur (la cause telle qu'il la lit, ce que ce client cherche, évite ou exclut) ; ce qu'il retient du retour de l'explorateur et comment présenter les compromis sans recommander ; une explication adaptée à l'expérience du client et reliée à son objectif et à son horizon ; la réécriture de son texte, une fois, quand les contrôles le signalent.
- **Ce qu'il ne fait pas** : aucun calcul, aucun verdict ni score à lui, aucune recommandation ; il ne teste aucune piste lui-même.
- **Ce qu'il rend** : l'explication en quatre parties (Verdict, Pourquoi, Ce qui est possible, Hypothèses et limites), 180 mots au plus.
- **Pourquoi le code seul ne suffit pas** : le code sait que la mesure « ampleur » vaut 39,6 ; il ne sait pas dire à une débutante qui veut préserver son capital sur 3 à 5 ans ce que cela veut dire pour elle, ni quoi dire à l'explorateur de ce qu'elle cherche.

## Agent explorateur : le chercheur de pistes

- **Mission** : pour un ordre en tension, chercher ce qui pourrait le rendre compatible avec la politique tout en gardant ce que le client cherchait.
- **Objectif** : deux à quatre pistes testées qui répondent à la cause et conviennent à ce client, chacune avec une phrase qui dit pourquoi elle a été essayée ; ou le constat simple qu'aucun ajustement raisonnable n'existe.
- **Quand il agit** : seulement quand le chef de dossier l'envoie, et seulement pour un ordre « en tension ».
- **Outils** : `lire_fiche_client`, `lire_fiche_instrument`, `decrire_apport` (des faits sur ce que l'instrument apporterait au portefeuille, et les candidats de la même classe classés par proximité), `lister_instruments`, `simuler_ordre`, `simuler_scenario`, `chercher_taille_compatible`. Chaque essai porte sa `raison`.
- **Ce qu'il décide** : d'abord, une lecture du cas côté client (fiche, politique, portefeuille, limites déjà proches) et côté ordre (l'instrument, son profil, ce qu'il ajouterait), d'où il tire la **finalité supposée** de l'achat, toujours comme une hypothèse ; quelles familles de pistes répondent à la cause, parmi quatre (un montant plus petit, un autre instrument, un achat partagé avec un fonds diversifié, un achat payé par la vente d'une autre position), et quelles **combinaisons** (un montant plus petit plus un complément, une partie payée par une vente) gardent le plus de cette finalité ; quels candidats apportent une exposition semblable et respectent les exclusions et préférences du client ; quelle position pourrait payer l'achat (une que la politique allégerait de toute façon, jamais une que le client recherche) ; comment s'adapter après un résultat, et quand il en sait assez.
- **Ce qu'il ne fait pas** : aucun calcul, verdict ou score ; aucune recommandation ; aucune piste qui vide le portefeuille.
- **Ce qu'il rend** au chef de dossier : la finalité supposée (son hypothèse), la cause lue, un bilan, et au plus quatre pistes, dont au moins une combinaison si l'une est compatible ; pour chacune sa famille, sa raison (ce qu'elle garde de la finalité) et le résultat du moteur. Il peut faire jusqu'à six essais et choisit ceux qu'il garde.
- **Pourquoi le code seul ne suffit pas** : `decrire_apport` donne des faits (corrélations, expositions, candidats proches) ; une table fixe « cause → piste » proposerait le même fonds à tous. Choisir un fonds qui garde l'exposition visée (technologie de croissance, banque canadienne…), écarter celui qu'un client évite, choisir la position à vendre et changer de piste après un résultat, c'est du jugement.

## Pas de troisième agent

Le contrôle des chiffres (code) et le garde-fou Bedrock (refus du conseil et des transactions réelles, ancrage contextuel) sont les seuls contrôles. Un agent vérificateur referait avec un modèle ce que ces contrôles font déjà sans modèle.

## Ce que fait le code

- Les trois premières lectures et la simulation de l'ordre passent par le moteur (`moteur/api.py`) ; chaque note, score, verdict et direction en vient.
- La **cause** du verdict (`cause` dans le résultat de la simulation) : la mesure qui décide et ce qui la fait, lue dans les notes déjà calculées.
- L'**envoi de l'explorateur** : refusé si une contrainte stricte est violée ou si l'ordre est compatible ; une seule fois par analyse.
- Les **faits** donnés à l'explorateur : l'ordre, son résultat et sa cause, le portefeuille, les thèmes et l'objectif du client.
- Les **bornes** : six essais au plus (l'outil refuse le septième), quatre pistes rendues au plus (les dernières testées si l'explorateur n'en désigne pas) ; dans un scénario, des ventes qui ne dépassent jamais le total des achats ni la position détenue ; une limite de tours pour chaque agent (8 pour le chef de dossier, 10 pour l'explorateur) ; un délai de 150 s pour l'explorateur.
- La liste **`pistes`** du rapport, construite à partir des résultats des outils, jamais du texte d'un agent.
- Les **contrôles** de l'explication : chaque chiffre doit venir d'un outil, puis le garde-fou Bedrock mesure l'ancrage.
- La **correction** : quand un contrôle signale le texte (un chiffre absent des outils, un passage non appuyé, plus de 180 mots), le code renvoie la liste des problèmes au chef de dossier, qui réécrit une seule fois ; le nouveau texte est vérifié à son tour, et l'avis reste si le problème demeure (`correction` dans le résultat).
- Le **repli** : si l'explorateur échoue ou dépasse son délai, le chef de dossier finit seul avec la taille compatible calculée par le code, et le rapport le dit.
- Le **suivi en direct** : chaque étape est envoyée à l'interface avec le nom de l'agent (`agent/suivi.py`).

Réglage : `GLC_EQUIPE=0` revient à l'agent seul d'avant (`agent/prompts/systeme.md`). Fichiers : `agent/prompts/principal.md`, `agent/prompts/explorateur.md`, `agent/inspection.py`, `agent/explorateur.py`, `agent/outils.py`.
