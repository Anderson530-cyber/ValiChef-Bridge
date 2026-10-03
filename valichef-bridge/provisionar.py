#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import secrets
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERSAO = "1.9.0"


def request_json(method, url, body=None, timeout=15):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"ValiChef-Bridge-Installer/{VERSAO}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"erro": raw or str(exc)}
        return exc.code, payload


def device_uid():
    machine_id = ""
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    except Exception:
        pass
    if not machine_id:
        machine_id = hashlib.sha256(
            f"{socket.gethostname()}:{os.getpid()}:{time.time_ns()}".encode()
        ).hexdigest()[:32]
    return f"vc-linux-{machine_id}"


def write_env(path, values):
    lines = [
        "# ValiChef Bridge - gerado automaticamente pelo instalador",
        "# Não compartilhe este arquivo. Ele contém a credencial local do Bridge.",
        "",
        f"VALICHEF_API_URL={values['api_url']}",
        f"VALICHEF_BRIDGE_SECRET={values['secret']}",
        f"VALICHEF_BRIDGE_ID={values['bridge_id']}",
        f"VALICHEF_RESTAURANTE_ID={values['restaurante_id']}",
        f"VALICHEF_IMPRESSORA_ID={values.get('impressora_id') or ''}",
        "",
        f"VALICHEF_PRINTER_HOST={values.get('printer_host') or ''}",
        f"VALICHEF_PRINTER_PORT={values.get('printer_port') or 9100}",
        "",
        "VALICHEF_HEARTBEAT_INTERVAL=30",
        "VALICHEF_QUEUE_INTERVAL=0.25",
        "VALICHEF_CAMERA_SESSION_INTERVAL=0.5",
        "VALICHEF_CAMERA_PASSWORDS_JSON={}",
        "",
    ]
    dest = Path(path)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, dest)
    os.chmod(dest, 0o600)


def main():
    parser = argparse.ArgumentParser(description="Provisionamento seguro do ValiChef Bridge")
    parser.add_argument("--api-url", default=os.environ.get("VALICHEF_API_URL", "https://app.valichef.com.br"))
    parser.add_argument("--env-file", default="/etc/valichef-bridge.env")
    parser.add_argument("--timeout-minutos", type=int, default=30)
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    uid = device_uid()
    secret = secrets.token_urlsafe(32)
    secret_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

    print()
    print("Iniciando ativação segura do ValiChef Bridge...")
    status, payload = request_json(
        "POST",
        f"{api_url}/api/bridge/provision",
        {
            "device_uid": uid,
            "secret_hash": secret_hash,
            "hostname": socket.gethostname(),
            "sistema_operacional": "linux",
            "versao": VERSAO,
        },
    )

    if status not in (200, 201):
        print("ERRO: não foi possível iniciar a ativação.")
        print(payload.get("erro") or payload.get("error") or payload)
        return 1

    codigo = str(payload.get("codigo_ativacao") or "")
    claim = str(payload.get("claim_token") or "")
    if not codigo or not claim:
        print("ERRO: servidor não devolveu as credenciais temporárias de ativação.")
        return 1

    print()
    print("============================================================")
    print("             CÓDIGO DE ATIVAÇÃO VALICHEF")
    print("============================================================")
    print()
    print(f"                     {codigo}")
    print()
    print("No Admin 110 Tech:")
    print("  Equipamentos > Ativar equipamento")
    print("  1. Digite o código acima")
    print("  2. Escolha o restaurante")
    print("  3. Escolha a impressora")
    print("  4. Confirme a ativação")
    print()
    print("O instalador está aguardando. Não feche esta janela.")
    print("============================================================")
    print()

    limite = time.time() + max(1, args.timeout_minutos) * 60
    consulta = urllib.parse.urlencode({"device_uid": uid, "claim_token": claim})
    ultimo_status = None

    while time.time() < limite:
        status, atual = request_json("GET", f"{api_url}/api/bridge/provision?{consulta}")
        estado = str(atual.get("status") or "")

        if estado != ultimo_status and estado:
            print(f"Status da ativação: {estado}")
            ultimo_status = estado

        if status == 200 and estado == "ativado":
            impressora = atual.get("impressora") or {}
            write_env(
                args.env_file,
                {
                    "api_url": api_url,
                    "secret": secret,
                    "bridge_id": atual.get("bridge_id") or "",
                    "restaurante_id": atual.get("restaurante_id") or "",
                    "impressora_id": atual.get("impressora_id") or "",
                    "printer_host": impressora.get("ip") or "",
                    "printer_port": impressora.get("porta") or 9100,
                },
            )
            print()
            print("Ativação concluída com sucesso.")
            print(f"Configuração gravada com segurança em {args.env_file}")
            if impressora:
                print(
                    "Impressora vinculada: "
                    + str(impressora.get("nome") or impressora.get("modelo") or impressora.get("id"))
                )
            else:
                print("Nenhuma impressora foi vinculada. Ela poderá ser configurada depois no Admin.")
            return 0

        if status == 410 or estado == "expirado":
            print("ERRO: o código de ativação expirou. Execute o instalador novamente.")
            return 2

        if status >= 400 and status not in (404,):
            print("Aguardando servidor de ativação...")
        time.sleep(4)

    print("ERRO: tempo de ativação esgotado. Execute o instalador novamente.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
