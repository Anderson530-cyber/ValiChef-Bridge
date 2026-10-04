#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="/home/valichef/valichef-bridge"
TARGET="$INSTALL_DIR/bridge.py"
URL="https://raw.githubusercontent.com/Anderson530-cyber/ValiChef-Bridge/main/valichef-bridge/bridge.py"
TMP="$(mktemp)"
BACKUP="$INSTALL_DIR/bridge.py.backup-update-$(date +%Y%m%d-%H%M%S)"
cleanup(){ rm -f "$TMP"; }
trap cleanup EXIT
sleep 2
curl -fsSL "$URL" -o "$TMP"
python3 -m py_compile "$TMP"
grep -q 'BRIDGE_VERSION' "$TMP"
cp "$TARGET" "$BACKUP"
cp "$TMP" "$TARGET"
chown valichef:valichef "$TARGET"
if ! systemctl restart valichef-bridge.service; then
  cp "$BACKUP" "$TARGET"
  chown valichef:valichef "$TARGET"
  systemctl restart valichef-bridge.service || true
  exit 1
fi
sleep 5
if ! curl -fsS http://127.0.0.1:5050/ >/dev/null; then
  cp "$BACKUP" "$TARGET"
  chown valichef:valichef "$TARGET"
  systemctl restart valichef-bridge.service || true
  exit 1
fi
