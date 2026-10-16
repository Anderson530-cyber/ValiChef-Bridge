#!/usr/bin/env bash
set -Eeuo pipefail
# Executado como root exclusivamente por regra sudoers de caminho exato.
# Agenda reboot para permitir ao Bridge responder ao backend primeiro.
[[ "${EUID}" -eq 0 ]] || exit 1
/usr/bin/systemd-run --unit=valichef-reboot --on-active=15s /usr/bin/systemctl reboot
