#!/usr/bin/env bash
set -Eeuo pipefail

APP_USER="valichef"
APP_HOME="/home/valichef"
APP_DIR="$APP_HOME/valichef-bridge"
ENV_FILE="/etc/valichef-bridge.env"
SERVICE_NAME="valichef-bridge.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/valichef-bridge"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute com sudo:"
  echo "  sudo ./instalar-valichef-bridge.sh"
  exit 1
fi

echo "========================================"
echo "     Instalador ValiChef Bridge 1.9.0"
echo "========================================"

if [[ ! -f "$SRC_DIR/bridge.py" || ! -f "$SRC_DIR/requirements.txt" ]]; then
  echo "ERRO: arquivos do Bridge não encontrados em $SRC_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/valichef-bridge.service" ]]; then
  echo "ERRO: valichef-bridge.service não encontrado."
  exit 1
fi

echo "[1/7] Instalando dependências do Ubuntu..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip ffmpeg

echo "[2/7] Preparando usuário e diretórios..."
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
fi
mkdir -p "$APP_DIR"
cp "$SRC_DIR/bridge.py" "$APP_DIR/bridge.py"
cp "$SRC_DIR/requirements.txt" "$APP_DIR/requirements.txt"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "[3/7] Criando ambiente Python..."
rm -rf "$APP_DIR/venv"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "[4/7] Instalando configuração..."
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$SRC_DIR/valichef-bridge.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo
  echo "ATENÇÃO: foi criado $ENV_FILE sem credenciais."
  echo "Preencha os dados de ativação do restaurante antes do uso definitivo."
else
  echo "Configuração existente preservada: $ENV_FILE"
fi

echo "[5/7] Instalando serviço systemd..."
cp "$SCRIPT_DIR/valichef-bridge.service" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "[6/7] Desativando suspensão/hibernação..."
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true

echo "[7/7] Iniciando Bridge..."
systemctl restart "$SERVICE_NAME"

echo
echo "========================================"
echo "Instalação concluída."
echo "========================================"
systemctl --no-pager --full status "$SERVICE_NAME" || true
echo
echo "Configuração: $ENV_FILE"
echo "Logs: journalctl -u $SERVICE_NAME -f"
