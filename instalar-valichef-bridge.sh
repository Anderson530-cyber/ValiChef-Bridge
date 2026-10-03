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
echo "     Instalador ValiChef Bridge 1.10.0"
echo "========================================"

if [[ ! -f "$SRC_DIR/bridge.py" || ! -f "$SRC_DIR/requirements.txt" || ! -f "$SRC_DIR/provisionar.py" ]]; then
  echo "ERRO: arquivos do Bridge não encontrados em $SRC_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/valichef-bridge.service" ]]; then
  echo "ERRO: valichef-bridge.service não encontrado."
  exit 1
fi

echo "[1/8] Instalando dependências do Ubuntu..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip ffmpeg ca-certificates

echo "[2/8] Preparando usuário e diretórios..."
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
fi
mkdir -p "$APP_DIR"
cp "$SRC_DIR/bridge.py" "$APP_DIR/bridge.py"
cp "$SRC_DIR/requirements.txt" "$APP_DIR/requirements.txt"
cp "$SRC_DIR/provisionar.py" "$APP_DIR/provisionar.py"
chmod 700 "$APP_DIR/provisionar.py"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "[3/8] Criando ambiente Python..."
rm -rf "$APP_DIR/venv"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "[4/8] Verificando ativação..."
CONFIG_COMPLETA=false
if [[ -f "$ENV_FILE" ]] \
  && grep -q '^VALICHEF_BRIDGE_SECRET=.' "$ENV_FILE" \
  && grep -q '^VALICHEF_BRIDGE_ID=.' "$ENV_FILE" \
  && grep -q '^VALICHEF_RESTAURANTE_ID=.' "$ENV_FILE"; then
  CONFIG_COMPLETA=true
fi

if [[ "$CONFIG_COMPLETA" == "true" ]]; then
  echo "Configuração existente e ativada preservada: $ENV_FILE"
else
  rm -f "$ENV_FILE"
  VALICHEF_API_URL="${VALICHEF_API_URL:-https://app.valichef.com.br}"
  "$APP_DIR/venv/bin/python" "$APP_DIR/provisionar.py" \
    --api-url "$VALICHEF_API_URL" \
    --env-file "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

echo "[5/8] Instalando serviço systemd..."
cp "$SCRIPT_DIR/valichef-bridge.service" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "[6/8] Desativando suspensão/hibernação..."
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true

echo "[7/8] Iniciando Bridge..."
systemctl restart "$SERVICE_NAME"

echo "[8/8] Validando serviço local..."
sleep 2
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "ERRO: o Bridge não permaneceu ativo."
  systemctl --no-pager --full status "$SERVICE_NAME" || true
  exit 1
fi

echo
echo "========================================"
echo "Instalação concluída."
echo "========================================"
systemctl --no-pager --full status "$SERVICE_NAME" || true
echo
echo "Configuração: $ENV_FILE"
echo "Logs: journalctl -u $SERVICE_NAME -f"
echo
echo "========================================"
echo "CHECKLIST OBRIGATÓRIO DE BIOS / ENERGIA"
echo "========================================"
echo "O instalador NÃO consegue alterar a BIOS automaticamente."
echo
echo "No mini PC homologado:"
echo "  1) Chipset > SoC Configuration"
echo "     Restore AC Power Loss = Power On"
echo "  2) Advanced > Power Management Setup"
echo "     EuP Function = Disabled"
echo
echo "IMPORTANTE: neste hardware, Power On sozinho não bastou;"
echo "o auto power-on só funcionou com EuP Function = Disabled."
echo
echo "Teste final obrigatório:"
echo "  - deixe o Ubuntu iniciar completamente"
echo "  - corte a energia com o mini PC ligado"
echo "  - aguarde pelo menos 10 segundos"
echo "  - restaure a energia sem apertar o botão Power"
echo "  - confirme que o mini PC liga sozinho"
echo "  - confirme Bridge + impressora online no Admin 110 Tech"
echo "  - imprima uma etiqueta pela web"
echo
echo "Somente depois desse teste o mini PC deve ser considerado homologado."
