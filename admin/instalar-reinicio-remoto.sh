#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "Execute com sudo"; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -o root -g root -m 0755 "$SCRIPT_DIR/reiniciar-mini-pc.sh" /usr/local/sbin/valichef-reiniciar-mini-pc
printf '%s\n' 'valichef ALL=(root) NOPASSWD: /usr/local/sbin/valichef-reiniciar-mini-pc' > /etc/sudoers.d/valichef-reiniciar-mini-pc
chmod 0440 /etc/sudoers.d/valichef-reiniciar-mini-pc
visudo -cf /etc/sudoers.d/valichef-reiniciar-mini-pc
echo "Permissao de reinicio remoto instalada. Testar somente em janela de manutencao."
