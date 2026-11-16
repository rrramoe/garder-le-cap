# Déploiement public

L'application tourne sur une petite instance EC2 Graviton (`t4g.medium`, Amazon Linux 2023, `us-east-1`). Streamlit y tourne comme service systemd, sur le port 80. Les droits de l'instance viennent d'un rôle IAM qui lui est propre : appel des deux modèles Bedrock (profils d'inférence globaux) et du garde-fou, lecture du bucket S3 privé, Systems Manager. Aucune clé n'est posée sur la machine. Le code arrive en archive `git archive` du commit choisi, avec les données non publiées (`data/*.csv` ignorés par git) et `glc.env`, par le bucket privé (préfixe `deploiement/`). Les commandes passent par Systems Manager : aucun port SSH n'est ouvert, et seul le port 80 l'est au monde. À chaque mise à jour, les fichiers `reference/*.json` suivis par git dans le commit déployé sont recopiés dans le bucket, que l'application lit. Une IP élastique garde la même adresse d'une mise à jour à l'autre. Le gel est inscrit dans le script : après le 15 novembre 2026 à 23 h 59 (heure de l'Est), `creer` et `mettre-a-jour` refusent de s'exécuter.

```bash
python deploiement/glc_deploiement.py creer                # rôle, groupe de sécurité (fermé), instance, IP élastique
python deploiement/glc_deploiement.py mettre-a-jour main --rechauffer   # ou un sha : déploie ce commit (quelques secondes), puis préchauffe les analyses des clients enregistrés
python deploiement/glc_deploiement.py ouvrir               # ouvre le port 80 au monde (ce port seulement)
python deploiement/glc_deploiement.py verifier --analyse --distant   # état, commit, vraie analyse sur la machine et par l'adresse publique
python deploiement/glc_deploiement.py commit               # commit en service
python deploiement/glc_deploiement.py creer-cloudfront     # adresse HTTPS devant l'instance (idempotent)
python deploiement/glc_deploiement.py supprimer-cloudfront # désactive puis supprime la distribution (10 à 15 min)
python deploiement/glc_deploiement.py supprimer            # retire tout ce qui suit, CloudFront compris
```

Les identifiants de ce poste sont ceux de `~/.aws/datathon.env` (voir `agent/identifiants.py`), et les noms des ressources sont ceux de `glc.env`.

**Adresse HTTPS.** Chrome refuse aujourd'hui une adresse en HTTP simple, ou affiche un avertissement avant de l'ouvrir. L'adresse publique passe donc par une distribution Amazon CloudFront (`https://<id>.cloudfront.net/`, certificat par défaut de CloudFront). CloudFront joint l'instance en HTTP sur le port 80 et redirige le visiteur de HTTP vers HTTPS. La distribution ne garde rien en cache (politique gérée CachingDisabled) et transmet tout ce que le visiteur envoie (politique gérée AllViewer : en-tête Host, cookies, chaînes de requête, passage au WebSocket de `/_stcore/stream`). Le délai de réponse de l'origine et le maintien de la connexion sont à 60 s, la classe de prix est 100, et rien n'est journalisé. Pendant une analyse, le WebSocket reste ouvert grâce aux pings du serveur Streamlit (toutes les 30 s, réglage par défaut) et aux étapes envoyées en direct. Le plus long silence mesuré pendant une vraie analyse est de 12 s, sous le délai de 60 s. Streamlit accepte le WebSocket derrière le nouveau nom sans aucun réglage changé : avec AllViewer, l'en-tête Host et l'origine correspondent. L'adresse HTTPS est écrite dans `glc.env` (`GLC_URL_HTTPS`, non publié). L'adresse HTTP de l'instance reste en service, en secours.

## Ressources AWS créées (par type)

- **Amazon EC2** : une instance `t4g.medium` (arm64, Amazon Linux 2023) avec un volume EBS gp3 chiffré de 16 Gio, une IP élastique et un groupe de sécurité `glc-deploiement-web` (entrée : TCP 80 seulement) dans le VPC par défaut.
- **AWS IAM** : un rôle `glc-deploiement-instance` (politique en ligne : `bedrock:InvokeModel*` sur les deux modèles, `bedrock:ApplyGuardrail` sur le garde-fou, `s3:GetObject` sur `reference/*` et `deploiement/*` du bucket ; politique gérée `AmazonSSMManagedInstanceCore`) et son profil d'instance.
- **AWS Systems Manager** : Run Command (`AWS-RunShellScript`) pour l'amorçage, les mises à jour et les vérifications.
- **Amazon S3** : sous le préfixe `deploiement/` du bucket privé existant, l'archive du code par commit, les données privées, `glc.env` et le script d'essai.
- **Amazon CloudFront** : une distribution (certificat par défaut, classe de prix 100, aucun cache, origine = nom DNS public de l'instance en HTTP sur le port 80).
- **Amazon Bedrock** : les deux modèles et le garde-fou existants, appelés par l'instance avec son rôle.

Toutes les ressources portent l'étiquette `Composant=glc-deploiement`.
