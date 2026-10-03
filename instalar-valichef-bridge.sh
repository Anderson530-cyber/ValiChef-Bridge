#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="valichef-bridge"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/valichef-bridge"
DEST_DIR="/opt/valichef/bridge"
SERVICE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/valichef-bridge.service"
SERVICE_DEST="/etc/systemd/system/valichef-bridge.service"
ENV_DIR="/etc/valichef-bridge"
START_FILE="${DEST_DIR}/start.sh"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute este instalador com sudo:"
  echo "  sudo ./instalar-valichef-bridge.sh"
  exit 1
fi

echo "== ValiChef Bridge Installer =="

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "ERRO: pasta valichef-bridge/ não encontrada."
  exit 1
fi

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "ERRO: arquivo valichef-bridge.service não encontrado."
  exit 1
fi

mkdir -p "${DEST_DIR}" "${ENV_DIR}"
cp -a "${SRC_DIR}/." "${DEST_DIR}/"
cp "${SERVICE_SRC}" "${SERVICE_DEST}"

# Gera o start.sh conforme o tipo de arquivo encontrado.
if [[ -x "${DEST_DIR}/valichef-bridge" ]]; then
  cat > "${START_FILE}" <<'EOF'
#!/usr/bin/env bash
exec /opt/valichef/bridge/valichef-bridge
EOF
elif [[ -f "${DEST_DIR}/index.js" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "ERRO: Node.js não está instalado."
    exit 1
  fi
  cat > "${START_FILE}" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/env node /opt/valichef/bridge/index.js
EOF
elif [[ -f "${DEST_DIR}/bridge.js" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "ERRO: Node.js não está instalado."
    exit 1
  fi
  cat > "${START_FILE}" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/env node /opt/valichef/bridge/bridge.js
EOF
elif [[ -f "${DEST_DIR}/main.py" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERRO: Python 3 não está instalado."
    exit 1
  fi
  cat > "${START_FILE}" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/env python3 /opt/valichef/bridge/main.py
EOF
else
  echo "ERRO: não encontrei o executável principal do Bridge."
  echo "Esperado: valichef-bridge, index.js, bridge.js ou main.py."
  echo "Adicione os arquivos reais do Bridge em valichef-bridge/ e execute novamente."
  exit 1
fi

chmod +x "${START_FILE}"
[[ -f "${DEST_DIR}/valichef-bridge" ]] && chmod +x "${DEST_DIR}/valichef-bridge" || true

# Evita suspensão/hibernação no mini PC operacional.
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true

systemctl daemon-reload
systemctl enable valichef-bridge.service
systemctl restart valichef-bridge.service

echo
echo "Instalação concluída."
echo "Status do serviço:"
systemctl --no-pager --full status valichef-bridge.service || true
echo
echo "Para acompanhar os logs:"
echo "  journalctl -u valichef-bridge -f"
