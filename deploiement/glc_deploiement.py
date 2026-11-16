"""Déploiement public de Garder le cap : une petite instance EC2 (us-east-1) qui sert l'application Streamlit.

    python deploiement/glc_deploiement.py creer              # rôle, groupe de sécurité (fermé), instance, IP élastique
    python deploiement/glc_deploiement.py mettre-a-jour REF  # déploie le commit REF (sha, branche, tag) en une commande
    python deploiement/glc_deploiement.py ouvrir             # ouvre le port 80 au monde (ce port seulement)
    python deploiement/glc_deploiement.py fermer             # referme le port 80
    python deploiement/glc_deploiement.py verifier [--analyse] [--distant]
                                                            # état, commit, page vue de l'extérieur, vraies analyses
    python deploiement/glc_deploiement.py commit             # commit qui tourne
    python deploiement/glc_deploiement.py creer-traces       # journal CloudWatch et droit d'écrire les traces
    python deploiement/glc_deploiement.py creer-cloudfront   # adresse HTTPS : distribution CloudFront devant l'instance
    python deploiement/glc_deploiement.py supprimer-cloudfront  # la désactive puis la supprime (10 à 15 min)
    python deploiement/glc_deploiement.py supprimer          # retire toutes les ressources créées (CloudFront compris)

Les droits de l'instance (Bedrock : les deux modèles et le garde-fou ; S3 : le bucket privé) viennent d'un rôle IAM :
aucune clé n'est posée sur la machine. Le code (archive `git archive` du commit), les données non publiées
(`data/*.csv` ignorés par git) et `glc.env` passent par le bucket S3 privé, sous `deploiement/`; les commandes passent
par Systems Manager (aucun port SSH ouvert). Les identifiants de ce poste sont lus comme le fait l'application
(`agent/identifiants.py`). Aucun identifiant, numéro de compte ni nom de ressource privée n'est écrit dans ce dépôt.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import boto3  # noqa: E402

from agent import identifiants  # noqa: E402
from moteur import configuration, references  # noqa: E402

REGION = "us-east-1"
NOM = "glc-deploiement"
ROLE = "glc-deploiement-instance"
GROUPE = "glc-deploiement-web"
TYPE_INSTANCE = "t4g.medium"   # 2 vCPU Graviton, 4 Gio : l'application et ses agents tiennent à l'aise
AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
PORT = 80
ETIQUETTES = [{"Key": "Projet", "Value": "garder-le-cap"}, {"Key": "Composant", "Value": NOM}]
PREFIXE = "deploiement/"
DONNEES_PRIVEES = ("prices_daily.csv", "corporate_actions.csv", "macro_rates.csv")
MODELES = ("amazon.nova-2-lite-v1:0", "anthropic.claude-sonnet-5*")
POLITIQUE_SSM = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
POLITIQUE_TRACES = "glc-deploiement-traces"
GROUPE_JOURNAUX = "/garder-le-cap/analyses"   # un journal CloudWatch Logs pour le projet
RETENTION_JOURS = 7
PREFIXE_TRACES = "traces/"
ETATS_VIVANTS = ["pending", "running", "stopping", "stopped"]
# Règle des organisateurs : aucune modification de l'outil après le dimanche 15 novembre 2026, 23 h 59 (heure de l'Est).
GEL = datetime(2026, 11, 16, 4, 59, tzinfo=timezone.utc)


def verifier_gel(maintenant: datetime | None = None) -> None:
    if (maintenant or datetime.now(timezone.utc)) >= GEL:
        sys.exit("Gel : aucune modification du déploiement après le 15 novembre 2026, 23 h 59 (heure de l'Est).")


# ---------------------------------------------------------------- outils

def client(service: str):
    return boto3.client(service, region_name=REGION)


def code_erreur(e: Exception) -> str:
    r = getattr(e, "response", None)
    return (r or {}).get("Error", {}).get("Code") or type(e).__name__


def bucket() -> str:
    b = configuration.valeur("GLC_BUCKET")
    if not b:
        sys.exit("GLC_BUCKET absent (glc.env) : le bucket privé est créé par scripts/creer_bucket.py.")
    return b


def compte() -> str:
    return client("sts").get_caller_identity()["Account"]


def politique_traces(compte_id: str, bucket_nom: str) -> dict:
    """Écriture seule des traces d'analyse : un objet sous `traces/` du bucket, une ligne dans le journal du projet.
    Ni lecture, ni liste, ni suppression ; rien hors de ce préfixe et de ce journal."""
    groupe = f"arn:aws:logs:{REGION}:{compte_id}:log-group:{GROUPE_JOURNAUX}"
    return {"Version": "2012-10-17", "Statement": [
        {"Sid": "TracesEcritureSeule", "Effect": "Allow", "Action": ["s3:PutObject"],
         "Resource": [f"arn:aws:s3:::{bucket_nom}/{PREFIXE_TRACES}*"]},
        {"Sid": "JournalAnalyses", "Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
         "Resource": [f"{groupe}:*", f"{groupe}:log-stream:*"]},
    ]}


def creer_traces(args=None) -> None:
    """Journal CloudWatch du projet (rétention 7 jours) et droit d'écrire les traces, sur le rôle de l'instance."""
    verifier_gel()
    logs = client("logs")
    try:
        logs.create_log_group(logGroupName=GROUPE_JOURNAUX, tags={e["Key"]: e["Value"] for e in ETIQUETTES})
        print(f"Journal CloudWatch {GROUPE_JOURNAUX} créé.")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"Journal CloudWatch {GROUPE_JOURNAUX} existant réutilisé.")
    logs.put_retention_policy(logGroupName=GROUPE_JOURNAUX, retentionInDays=RETENTION_JOURS)
    boto3.client("iam").put_role_policy(RoleName=ROLE, PolicyName=POLITIQUE_TRACES,
                                        PolicyDocument=json.dumps(politique_traces(compte(), bucket())))
    print(f"Politique {POLITIQUE_TRACES} posée sur le rôle {ROLE}.")
    configuration.ecrire_valeurs({"GLC_JOURNAL_GROUPE": GROUPE_JOURNAUX})
    print(f"GLC_JOURNAL_GROUPE écrit dans {configuration.chemin_fichier().name} (déposé sur la machine par "
          "`mettre-a-jour --fichiers`).")


def politique_instance(compte_id: str, bucket_nom: str) -> dict:
    """Droits minimaux de l'instance : les deux modèles (profils d'inférence globaux), le garde-fou, le bucket."""
    gid = configuration.valeur("GLC_GARDE_FOU_ID") or "*"
    modeles = [f"arn:aws:bedrock:*::foundation-model/{m}" for m in MODELES]
    profils = [f"arn:aws:bedrock:{REGION}:{compte_id}:inference-profile/global.{m}" for m in MODELES]
    return {"Version": "2012-10-17", "Statement": [
        {"Sid": "Modeles", "Effect": "Allow",
         "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], "Resource": modeles + profils},
        {"Sid": "GardeFou", "Effect": "Allow", "Action": ["bedrock:ApplyGuardrail"],
         "Resource": [f"arn:aws:bedrock:{REGION}:{compte_id}:guardrail/{gid}"]},
        {"Sid": "BucketLecture", "Effect": "Allow", "Action": ["s3:GetObject"],
         "Resource": [f"arn:aws:s3:::{bucket_nom}/reference/*", f"arn:aws:s3:::{bucket_nom}/{PREFIXE}*"]},
        {"Sid": "BucketListe", "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": [f"arn:aws:s3:::{bucket_nom}"],
         "Condition": {"StringLike": {"s3:prefix": ["reference/*", f"{PREFIXE}*"]}}},
    ]}


def instance():
    r = client("ec2").describe_instances(Filters=[
        {"Name": "tag:Composant", "Values": [NOM]}, {"Name": "instance-state-name", "Values": ETATS_VIVANTS}])
    trouvees = [i for res in r["Reservations"] for i in res["Instances"]]
    return trouvees[0] if trouvees else None


def groupe_id():
    r = client("ec2").describe_security_groups(Filters=[{"Name": "group-name", "Values": [GROUPE]}])
    return r["SecurityGroups"][0]["GroupId"] if r["SecurityGroups"] else None


def ip_elastique():
    r = client("ec2").describe_addresses(Filters=[{"Name": "tag:Composant", "Values": [NOM]}])
    return r["Addresses"][0] if r["Addresses"] else None


def adresse_publique() -> str | None:
    a = ip_elastique()
    if a:
        return a["PublicIp"]
    i = instance()
    return i.get("PublicIpAddress") if i else None


def url() -> str | None:
    ip = adresse_publique()
    if not ip:
        return None
    return f"http://ec2-{ip.replace('.', '-')}.compute-1.amazonaws.com/"


def ssm(commandes: list[str], delai_s: int = 900, afficher: bool = True) -> tuple[bool, str]:
    """Exécute un script shell sur l'instance par Systems Manager ; renvoie (succès, sortie)."""
    i = instance()
    if not i:
        sys.exit("Aucune instance : lancez d'abord `creer`.")
    s = client("ssm")
    cid = s.send_command(InstanceIds=[i["InstanceId"]], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": commandes, "executionTimeout": [str(delai_s)]},
                         TimeoutSeconds=max(60, delai_s))["Command"]["CommandId"]
    fin = time.monotonic() + delai_s + 60
    while time.monotonic() < fin:
        time.sleep(3)
        try:
            r = s.get_command_invocation(CommandId=cid, InstanceId=i["InstanceId"])
        except Exception as e:
            if code_erreur(e) == "InvocationDoesNotExist":
                continue
            raise
        if r["Status"] not in ("Pending", "InProgress", "Delayed"):
            sortie = (r.get("StandardOutputContent") or "") + (r.get("StandardErrorContent") or "")
            if afficher and sortie.strip():
                print(sortie.rstrip())
            return r["Status"] == "Success", sortie
    return False, "délai dépassé"


def attendre_ssm(delai_s: int = 600) -> None:
    i = instance()
    fin = time.monotonic() + delai_s
    while time.monotonic() < fin:
        r = client("ssm").describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [i["InstanceId"]]}])
        if r["InstanceInformationList"] and r["InstanceInformationList"][0]["PingStatus"] == "Online":
            return
        time.sleep(10)
    sys.exit("L'instance ne répond pas à Systems Manager.")


def http(chemin: str, delai_s: int = 10, base: str | None = None) -> tuple[int, str]:
    adresse = base or url()
    try:
        with urllib.request.urlopen(adresse.rstrip("/") + chemin, timeout=delai_s) as r:
            return r.status, r.read(4000).decode("utf-8", "replace")
    except Exception as e:
        return 0, type(e).__name__


# ---------------------------------------------------------------- creer

def creer_role() -> None:
    iam = boto3.client("iam")
    confiance = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"},
                                                         "Action": "sts:AssumeRole"}]}
    try:
        iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(confiance), Tags=ETIQUETTES,
                        Description="Garder le cap : instance de démonstration (Bedrock, bucket privé, SSM)")
        print("Rôle IAM créé.")
    except iam.exceptions.EntityAlreadyExistsException:
        print("Rôle IAM existant réutilisé.")
    iam.put_role_policy(RoleName=ROLE, PolicyName=NOM, PolicyDocument=json.dumps(politique_instance(compte(), bucket())))
    iam.attach_role_policy(RoleName=ROLE, PolicyArn=POLITIQUE_SSM)
    try:
        iam.create_instance_profile(InstanceProfileName=ROLE, Tags=ETIQUETTES)
        iam.add_role_to_instance_profile(InstanceProfileName=ROLE, RoleName=ROLE)
        print("Profil d'instance créé.")
        time.sleep(10)  # propagation IAM avant le lancement
    except iam.exceptions.EntityAlreadyExistsException:
        pass


def creer_groupe() -> str:
    gid = groupe_id()
    if gid:
        return gid
    ec2 = client("ec2")
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    gid = ec2.create_security_group(GroupName=GROUPE, VpcId=vpc, Description="Garder le cap : port web seulement",
                                    TagSpecifications=[{"ResourceType": "security-group", "Tags": ETIQUETTES}])["GroupId"]
    print("Groupe de sécurité créé (fermé : aucune entrée).")
    return gid


def deposer_fichiers() -> None:
    """Données non publiées, configuration locale et script d'essai : vers le bucket privé, jamais vers le dépôt."""
    s3, b = client("s3"), bucket()
    for nom in DONNEES_PRIVEES:
        chemin = RACINE / "data" / nom
        if chemin.is_file():
            s3.upload_file(str(chemin), b, f"{PREFIXE}donnees/{nom}")
        else:
            print(f"Attention : data/{nom} absent de ce poste, non déposé.")
    s3.upload_file(str(configuration.chemin_fichier()), b, f"{PREFIXE}glc.env")
    s3.upload_file(str(Path(__file__).with_name("essai_analyse.py")), b, f"{PREFIXE}essai_analyse.py")
    print("Données privées, glc.env et script d'essai déposés dans le bucket privé.")


def creer(args) -> None:
    verifier_gel()
    creer_role()
    creer_traces()
    gid = creer_groupe()
    deposer_fichiers()
    i = instance()
    ec2 = client("ec2")
    if not i:
        ami = client("ssm").get_parameter(Name=AMI_PARAM)["Parameter"]["Value"]
        for essai in range(6):
            try:
                i = ec2.run_instances(
                    ImageId=ami, InstanceType=TYPE_INSTANCE, MinCount=1, MaxCount=1, SecurityGroupIds=[gid],
                    IamInstanceProfile={"Name": ROLE}, UserData=Path(__file__).with_name("amorcage.sh").read_text(),
                    MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled"},
                    BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 16, "VolumeType": "gp3",
                                                                            "Encrypted": True, "DeleteOnTermination": True}}],
                    TagSpecifications=[{"ResourceType": t, "Tags": ETIQUETTES + [{"Key": "Name", "Value": NOM}]}
                                       for t in ("instance", "volume")])["Instances"][0]
                break
            except Exception as e:
                if code_erreur(e) == "InvalidParameterValue" and essai < 5:
                    time.sleep(10)  # profil d'instance pas encore visible
                    continue
                raise
        print(f"Instance {TYPE_INSTANCE} lancée.")
    ec2.get_waiter("instance_running").wait(InstanceIds=[i["InstanceId"]])
    a = ip_elastique()
    if not a:
        a = ec2.allocate_address(Domain="vpc", TagSpecifications=[{"ResourceType": "elastic-ip", "Tags": ETIQUETTES}])
        print("IP élastique allouée.")
    if a.get("InstanceId") != i["InstanceId"]:
        ec2.associate_address(AllocationId=a["AllocationId"], InstanceId=i["InstanceId"])
    print("Attente de Systems Manager et de l'amorçage…")
    attendre_ssm()
    ok, _ = ssm(["for i in $(seq 90); do test -f /opt/glc/amorcage-termine && exit 0; sleep 5; done; "
                 "tail -30 /var/log/cloud-init-output.log; exit 1"], delai_s=600)
    if not ok:
        sys.exit("Amorçage non terminé.")
    print(f"Instance prête (port fermé). Adresse future : {url()}")
    print("Suite : mettre-a-jour REF, verifier --analyse, puis ouvrir.")


# ---------------------------------------------------------------- mettre a jour

def resoudre(ref: str) -> str:
    return subprocess.run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=RACINE, check=True,
                          capture_output=True, text=True).stdout.strip()


def script_mise_a_jour(b: str, sha: str) -> list[str]:
    v = f"/opt/glc/versions/{sha}"
    return [
        "set -euo pipefail",
        "test -f /opt/glc/amorcage-termine",
        "export UV_CACHE_DIR=/opt/glc/.cache/uv UV_PYTHON_INSTALL_DIR=/opt/glc/python",
        f"if [ ! -f {v}/app.py ]; then rm -rf {v}.tmp {v}; mkdir -p {v}.tmp; "
        f"aws s3 cp --only-show-errors s3://{b}/{PREFIXE}code/{sha}.tar.gz - | tar -xz -C {v}.tmp; mv {v}.tmp {v}; fi",
        f"mkdir -p {v}/data",
        f"aws s3 cp --only-show-errors --recursive s3://{b}/{PREFIXE}donnees/ {v}/data/",
        f"aws s3 cp --only-show-errors s3://{b}/{PREFIXE}glc.env {v}/glc.env",
        f"aws s3 cp --only-show-errors s3://{b}/{PREFIXE}essai_analyse.py /opt/glc/essai_analyse.py",
        f"echo {sha} > {v}/COMMIT_DEPLOYE",
        "test -x /opt/glc/venv/bin/python || uv venv --quiet --python 3.13 /opt/glc/venv",
        f"uv pip install --quiet --python /opt/glc/venv/bin/python -r {v}/requirements.txt",
        "chown -R glc:glc /opt/glc",
        f"ln -sfn {v} /opt/glc/courant.nouveau && mv -Tf /opt/glc/courant.nouveau /opt/glc/courant",
        # Le commit en service, donné à l'application (traces : GLC_VERSION_APPLICATION).
        "mkdir -p /etc/systemd/system/glc.service.d",
        f"printf '[Service]\\nEnvironment=GLC_VERSION_APPLICATION={sha[:7]}\\n' > /etc/systemd/system/glc.service.d/version.conf",
        "systemctl daemon-reload",
        "systemctl restart glc",
        "for i in $(seq 60); do curl -fs -o /dev/null localhost/_stcore/health && break; sleep 2; done",
        "echo santé: $(curl -fsS localhost/_stcore/health)",
        "(cd /opt/glc/versions && ls -1t | grep -v -x " + sha + " | tail -n +5 | xargs -r rm -rf) || true",
        "echo commit en service: $(cat /opt/glc/courant/COMMIT_DEPLOYE)",
    ]


def synchroniser_references(b: str, sha: str) -> None:
    """L'application lit `reference/*.json` dans le bucket : on y met la version suivie par git du commit déployé
    (ce que fait scripts/creer_bucket.py depuis le dossier local). Les fichiers non suivis (profils des instruments)
    restent tels quels."""
    s3 = client("s3")
    noms = subprocess.run(["git", "ls-tree", "--name-only", sha, "reference/"], cwd=RACINE, check=True,
                          capture_output=True, text=True).stdout.split()
    changes = []
    for chemin in (n for n in noms if n.endswith(".json")):
        contenu = subprocess.run(["git", "show", f"{sha}:{chemin}"], cwd=RACINE, check=True, capture_output=True).stdout
        cle = references.cle_s3(Path(chemin).stem)
        try:
            actuel = s3.get_object(Bucket=b, Key=cle)["Body"].read()
        except Exception:
            actuel = None
        if actuel != contenu:
            s3.put_object(Bucket=b, Key=cle, Body=contenu, ContentType="application/json; charset=utf-8")
            changes.append(Path(chemin).name)
    print(f"Références du bucket alignées sur le commit : {', '.join(changes) if changes else 'déjà à jour'}.")


def mettre_a_jour(args) -> None:
    verifier_gel()
    sha = resoudre(args.ref)
    b = bucket()
    archive = subprocess.run(["git", "archive", "--format=tar.gz", sha], cwd=RACINE, check=True, capture_output=True).stdout
    client("s3").put_object(Bucket=b, Key=f"{PREFIXE}code/{sha}.tar.gz", Body=archive)
    if args.fichiers:
        deposer_fichiers()
    synchroniser_references(b, sha)
    print(f"Déploiement de {sha[:12]}…")
    debut = time.monotonic()
    ok, _ = ssm(script_mise_a_jour(b, sha), delai_s=900)
    if not ok:
        sys.exit("Échec de la mise à jour (l'ancienne version reste en service si le lien n'a pas été changé).")
    print(f"Commit {sha[:12]} en service en {time.monotonic() - debut:.0f} s. {url()}")
    if args.rechauffer:
        print("Préchauffage des analyses des clients enregistrés (scripts/rechauffer_analyses.py, sur la machine)…")
        ok, _ = ssm([f"cd /opt/glc/courant && test -f scripts/rechauffer_analyses.py && {ENV_SERVICE} "
                     "/opt/glc/venv/bin/python scripts/rechauffer_analyses.py"], delai_s=600)
        if not ok:
            sys.exit("Préchauffage en échec (l'application reste en service, sans mémoire préchauffée).")


# ---------------------------------------------------------------- ouvrir / fermer

REGLE = {"IpProtocol": "tcp", "FromPort": PORT, "ToPort": PORT, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "web"}]}


def ouvrir(args) -> None:
    try:
        client("ec2").authorize_security_group_ingress(GroupId=groupe_id(), IpPermissions=[REGLE])
    except Exception as e:
        if code_erreur(e) != "InvalidPermission.Duplicate":
            raise
    print(f"Port {PORT} ouvert au monde : {url()}")


def fermer(args) -> None:
    try:
        client("ec2").revoke_security_group_ingress(GroupId=groupe_id(), IpPermissions=[REGLE])
    except Exception as e:
        if code_erreur(e) != "InvalidPermission.NotFound":
            raise
    print(f"Port {PORT} fermé.")


# ---------------------------------------------------------------- verifier / commit

ENV_SERVICE = ("sudo -u glc env HOME=/opt/glc AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 "
               "GLC_AWS_ENV=/opt/glc/sans-fichier-d-identifiants "
               "GLC_VERSION_APPLICATION=$(cut -c1-7 /opt/glc/courant/COMMIT_DEPLOYE)")


def commit_en_service() -> str:
    ok, sortie = ssm(["cat /opt/glc/courant/COMMIT_DEPLOYE 2>/dev/null || echo aucun"], delai_s=60, afficher=False)
    return sortie.strip() if ok else "inconnu"


def commit(args) -> None:
    print(commit_en_service())


def verifier(args) -> int:
    i = instance()
    if not i:
        print("Aucune instance.")
        return 1
    ouvert = any(p.get("FromPort") == PORT for p in client("ec2").describe_security_groups(
        GroupIds=[groupe_id()])["SecurityGroups"][0]["IpPermissions"])
    print(f"Instance {i['InstanceType']} : {i['State']['Name']}; port {PORT} {'ouvert' if ouvert else 'fermé'}")
    print(f"Adresse : {url()}")
    print(f"Commit en service : {commit_en_service()}")
    ok_service, sortie = ssm(["systemctl is-active glc; curl -fsS localhost/_stcore/health"], delai_s=60, afficher=False)
    print(f"Sur la machine : {' / '.join(sortie.split())}")
    ok = ok_service
    if ouvert:
        sante, corps = http("/_stcore/health")
        page, html = http("/")
        vu = sante == 200 and page == 200 and "<title>Streamlit</title>" in html
        print(f"Vu de ce poste : santé {sante or corps}, page {page or html} → {'répond' if vu else 'NE RÉPOND PAS'}")
        ok &= vu
        https = url_https()
        if https:
            sante_s, _ = http("/_stcore/health", base=https)
            page_s, html_s = http("/", base=https)
            vu_s = sante_s == 200 and page_s == 200 and "<title>Streamlit</title>" in html_s
            print(f"HTTPS (CloudFront) {https} : santé {sante_s}, page {page_s} → {'répond' if vu_s else 'NE RÉPOND PAS'}")
            ok &= vu_s
        if args.distant:
            import asyncio
            from essai_distant import principal as essai_distant
            for adresse in [a for a in (https, url()) if a]:
                print(f"Vraie analyse par {adresse}, comme un navigateur…")
                ok &= asyncio.run(essai_distant(adresse)) == 0
    if args.analyse:
        print("Vraie analyse sur la machine (application, moteur, agents Bedrock, garde-fou, bucket)…")
        ok_a, _ = ssm([f"cd /opt/glc/courant && {ENV_SERVICE} GLC_RACINE=/opt/glc/courant "
                       "/opt/glc/venv/bin/python /opt/glc/essai_analyse.py"], delai_s=420)
        ok &= ok_a
    print("Bilan : " + ("tout répond" if ok else "PROBLÈME"))
    return 0 if ok else 1


# ---------------------------------------------------------------- CloudFront (adresse HTTPS)

CF_COMMENTAIRE = "Garder le cap : application publique en HTTPS (glc-deploiement)"
CF_ORIGINE = "glc-instance"
CACHING_DISABLED = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"   # politique gérée Managed-CachingDisabled
ALL_VIEWER = "216adef6-5c7f-47e4-b989-5492eafa07d3"         # politique gérée Managed-AllViewer


def distribution() -> dict | None:
    cf = boto3.client("cloudfront")
    for page in cf.get_paginator("list_distributions").paginate():
        for d in page["DistributionList"].get("Items", []) or []:
            if d.get("Comment") == CF_COMMENTAIRE:
                return d
    return None


def url_https() -> str | None:
    d = distribution()
    return f"https://{d['DomainName']}/" if d else None


def config_distribution(origine: str) -> dict:
    """Devant l'instance : HTTP vers l'origine (port 80), HTTPS pour le visiteur, aucun cache, tout l'en-tête du
    visiteur transmis (Host, cookies, chaînes de requête, passage au WebSocket de /_stcore/stream)."""
    return {
        "CallerReference": f"{NOM}-{int(time.time())}",
        "Comment": CF_COMMENTAIRE,
        "Enabled": True,
        "PriceClass": "PriceClass_100",
        "HttpVersion": "http2",
        "IsIPV6Enabled": True,
        "Origins": {"Quantity": 1, "Items": [{
            "Id": CF_ORIGINE, "DomainName": origine,
            "CustomOriginConfig": {"HTTPPort": PORT, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only",
                                   "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                                   "OriginReadTimeout": 60, "OriginKeepaliveTimeout": 60}}]},
        "DefaultCacheBehavior": {
            "TargetOriginId": CF_ORIGINE, "ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
            "AllowedMethods": {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                               "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
            "CachePolicyId": CACHING_DISABLED, "OriginRequestPolicyId": ALL_VIEWER},
        "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
    }


def creer_cloudfront(args) -> None:
    verifier_gel()
    d = distribution()
    if d:
        print("Distribution CloudFront existante réutilisée.")
    else:
        origine = url().split("/")[2]
        cf = boto3.client("cloudfront")
        d = cf.create_distribution_with_tags(DistributionConfigWithTags={
            "DistributionConfig": config_distribution(origine), "Tags": {"Items": ETIQUETTES}})["Distribution"]
        print("Distribution CloudFront créée ; déploiement en cours (quelques minutes)…")
        cf.get_waiter("distribution_deployed").wait(Id=d["Id"], WaiterConfig={"Delay": 20, "MaxAttempts": 60})
    adresse = f"https://{d['DomainName']}/"
    configuration.ecrire_valeurs({"GLC_URL_HTTPS": adresse})
    print(f"Adresse HTTPS : {adresse} (écrite dans {configuration.chemin_fichier().name}, non publié)")


def supprimer_cloudfront(args=None) -> None:
    """Désactive la distribution, attend qu'elle soit déployée désactivée, puis la supprime (10 à 15 min)."""
    d = distribution()
    if not d:
        print("Aucune distribution CloudFront.")
        return
    cf = boto3.client("cloudfront")
    r = cf.get_distribution_config(Id=d["Id"])
    config, etag = r["DistributionConfig"], r["ETag"]
    if config["Enabled"]:
        config["Enabled"] = False
        etag = cf.update_distribution(Id=d["Id"], DistributionConfig=config, IfMatch=etag)["ETag"]
        print("Distribution CloudFront désactivée ; attente de la propagation…")
    cf.get_waiter("distribution_deployed").wait(Id=d["Id"], WaiterConfig={"Delay": 30, "MaxAttempts": 60})
    cf.delete_distribution(Id=d["Id"], IfMatch=cf.get_distribution(Id=d["Id"])["ETag"])
    print("Distribution CloudFront supprimée.")


# ---------------------------------------------------------------- supprimer

def supprimer(args) -> None:
    supprimer_cloudfront()
    ec2, iam, s3 = client("ec2"), boto3.client("iam"), client("s3")
    i = instance()
    a = ip_elastique()
    if a and a.get("AssociationId"):
        ec2.disassociate_address(AssociationId=a["AssociationId"])
    if a:
        ec2.release_address(AllocationId=a["AllocationId"])
        print("IP élastique libérée.")
    if i:
        ec2.terminate_instances(InstanceIds=[i["InstanceId"]])
        print("Instance en cours d'arrêt définitif…")
        ec2.get_waiter("instance_terminated").wait(InstanceIds=[i["InstanceId"]])
        print("Instance supprimée (et son disque).")
    gid = groupe_id()
    if gid:
        ec2.delete_security_group(GroupId=gid)
        print("Groupe de sécurité supprimé.")
    try:
        iam.remove_role_from_instance_profile(InstanceProfileName=ROLE, RoleName=ROLE)
    except Exception:
        pass
    try:
        iam.delete_instance_profile(InstanceProfileName=ROLE)
        print("Profil d'instance supprimé.")
    except Exception:
        pass
    try:
        iam.delete_role_policy(RoleName=ROLE, PolicyName=NOM)
        iam.detach_role_policy(RoleName=ROLE, PolicyArn=POLITIQUE_SSM)
    except Exception:
        pass
    try:
        iam.delete_role_policy(RoleName=ROLE, PolicyName=POLITIQUE_TRACES)
    except Exception:
        pass
    try:
        client("logs").delete_log_group(logGroupName=GROUPE_JOURNAUX)
        print(f"Journal CloudWatch {GROUPE_JOURNAUX} supprimé.")
    except Exception:
        pass
    try:
        iam.delete_role(RoleName=ROLE)
        print("Rôle IAM supprimé.")
    except Exception:
        pass
    b = configuration.valeur("GLC_BUCKET")
    if b:
        cles = [{"Key": o["Key"]} for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=PREFIXE)
                for o in page.get("Contents", [])]
        for k in range(0, len(cles), 1000):
            s3.delete_objects(Bucket=b, Delete={"Objects": cles[k:k + 1000]})
        print(f"{len(cles)} objets {PREFIXE} retirés du bucket (le bucket de référence reste).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parser.add_subparsers(dest="action", required=True)
    sous.add_parser("creer").set_defaults(f=creer)
    m = sous.add_parser("mettre-a-jour")
    m.add_argument("ref", help="commit, branche ou tag de ce dépôt (par exemple main)")
    m.add_argument("--fichiers", action="store_true", help="redéposer aussi les données privées et glc.env")
    m.add_argument("--rechauffer", action="store_true",
                   help="préchauffer ensuite les analyses des clients enregistrés (1 à 2 min)")
    m.set_defaults(f=mettre_a_jour)
    sous.add_parser("ouvrir").set_defaults(f=ouvrir)
    sous.add_parser("fermer").set_defaults(f=fermer)
    v = sous.add_parser("verifier")
    v.add_argument("--analyse", action="store_true", help="lancer aussi une vraie analyse sur la machine (1 à 4 min)")
    v.add_argument("--distant", action="store_true",
                   help="lancer aussi une vraie analyse par l'adresse publique, depuis ce poste (1 à 4 min)")
    v.set_defaults(f=verifier)
    sous.add_parser("commit").set_defaults(f=commit)
    sous.add_parser("creer-traces").set_defaults(f=creer_traces)
    sous.add_parser("creer-cloudfront").set_defaults(f=creer_cloudfront)
    sous.add_parser("supprimer-cloudfront").set_defaults(f=supprimer_cloudfront)
    sous.add_parser("supprimer").set_defaults(f=supprimer)
    args = parser.parse_args()
    if not identifiants.charger_identifiants() and not identifiants.identifiants_disponibles():
        print("Identifiants AWS absents : copiez-les dans ~/.aws/datathon.env.")
        return 1
    try:
        return args.f(args) or 0
    except Exception as e:
        if code_erreur(e) == "ExpiredToken":
            print("Identifiants AWS expirés (ExpiredToken) : copiez-en de nouveaux dans ~/.aws/datathon.env.")
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
