# Déploiement public

L'application tourne sur une petite instance EC2 Graviton (`t4g.medium`, Amazon Linux 2023, `us-east-1`). Streamlit y tourne comme service systemd, sur le port 80. Les droits de l'instance viennent d'un rôle IAM qui lui est propre : appel des deux modèles Bedrock (profils d'inférence globaux) et du garde-fou, lecture du bucket S3 privé, Systems Manager. Aucune clé n'est posée sur la machine. Le code arrive en archive `git archive` du commit choisi, avec les données non publiées (`data/*.csv` ignorés par git) et `glc.env`, par le bucket privé (préfixe `deploiement/`). Les commandes passent par Systems Manager : aucun port SSH n'est ouvert, et seul le port 80 l'est au monde. À chaque mise à jour, les fichiers `reference/*.json` suivis par git dans le commit déployé sont recopiés dans le bucket, que l'application lit. Une IP élastique garde la même adresse d'une mise à jour à l'autre. Le gel est inscrit dans le script : après le 15 novembre 2026 à 23 h 59 (heure de l'Est), `creer` et `mettre-a-jour` refusent de s'exécuter.

```bash
python deploiement/glc_deploiement.py creer                # rôle, groupe de sécurité (fermé), instance, IP élastique
python deploiement/glc_deploiement.py mettre-a-jour main   # ou un sha : déploie ce commit (quelques secondes)
python deploiement/glc_deploiement.py ouvrir               # ouvre le port 80 au monde (ce port seulement)
python deploiement/glc_deploiement.py verifier --analyse --distant   # état, commit, vraie analyse sur la machine et par l'adresse publique
python deploiement/glc_deploiement.py commit               # commit en service
python deploiement/glc_deploiement.py supprimer            # retire tout ce qui suit
```

Les identifiants de ce poste sont ceux de `~/.aws/datathon.env` (voir `agent/identifiants.py`), et les noms des ressources sont ceux de `glc.env`.

## Ressources AWS créées (par type)

- **Amazon EC2** : une instance `t4g.medium` (arm64, Amazon Linux 2023) avec un volume EBS gp3 chiffré de 16 Gio, une IP élastique et un groupe de sécurité `glc-deploiement-web` (entrée : TCP 80 seulement) dans le VPC par défaut.
- **AWS IAM** : un rôle `glc-deploiement-instance` (politique en ligne : `bedrock:InvokeModel*` sur les deux modèles, `bedrock:ApplyGuardrail` sur le garde-fou, `s3:GetObject` sur `reference/*` et `deploiement/*` du bucket ; politique gérée `AmazonSSMManagedInstanceCore`) et son profil d'instance.
- **AWS Systems Manager** : Run Command (`AWS-RunShellScript`) pour l'amorçage, les mises à jour et les vérifications.
- **Amazon S3** : sous le préfixe `deploiement/` du bucket privé existant, l'archive du code par commit, les données privées, `glc.env` et le script d'essai.
- **Amazon Bedrock** : les deux modèles et le garde-fou existants, appelés par l'instance avec son rôle.

Toutes les ressources portent l'étiquette `Composant=glc-deploiement`.
