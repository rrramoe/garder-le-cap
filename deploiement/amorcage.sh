#!/bin/bash
# Amorçage de l'instance (user-data EC2). Générique : aucun nom de ressource, aucun identifiant.
# Le code, les données et la configuration arrivent ensuite par `glc_deploiement.py mettre-a-jour`
# (Systems Manager + bucket S3 privé). Les droits AWS viennent du rôle de l'instance.
set -euxo pipefail

dnf install -y tar gzip awscli-2
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

id glc >/dev/null 2>&1 || useradd --system --home-dir /opt/glc --shell /sbin/nologin glc
mkdir -p /opt/glc/versions
chown -R glc:glc /opt/glc

cat > /etc/systemd/system/glc.service <<'UNIT'
[Unit]
Description=Garder le cap (Streamlit)
After=network-online.target
Wants=network-online.target
ConditionPathExists=/opt/glc/courant/app.py

[Service]
User=glc
Group=glc
WorkingDirectory=/opt/glc/courant
Environment=HOME=/opt/glc
Environment=AWS_REGION=us-east-1
Environment=AWS_DEFAULT_REGION=us-east-1
Environment=GLC_AWS_ENV=/opt/glc/sans-fichier-d-identifiants
ExecStart=/opt/glc/venv/bin/streamlit run app.py --server.port 80 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable glc.service
touch /opt/glc/amorcage-termine
