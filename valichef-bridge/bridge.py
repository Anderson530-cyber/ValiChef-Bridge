from flask import Flask, jsonify, request
from flask_cors import CORS

import json
import asyncio
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

app = Flask(__name__)
CORS(app)

BRIDGE_VERSION = "1.11.0"
VALICHEF_API_URL = os.environ.get("VALICHEF_API_URL", "").rstrip("/")
VALICHEF_BRIDGE_SECRET = os.environ.get("VALICHEF_BRIDGE_SECRET", "")
VALICHEF_BRIDGE_ID = os.environ.get("VALICHEF_BRIDGE_ID", "")
HEARTBEAT_INTERVAL = max(5, min(int(os.environ.get("VALICHEF_HEARTBEAT_INTERVAL", "10")), 10))
VALICHEF_RESTAURANTE_ID = os.environ.get("VALICHEF_RESTAURANTE_ID", "")
VALICHEF_IMPRESSORA_ID = os.environ.get("VALICHEF_IMPRESSORA_ID", "")

# A impressora fica em configuracao, nao presa ao codigo.
PRINTER_HOST = os.environ.get("VALICHEF_PRINTER_HOST", "")
PRINTER_PORT = int(os.environ.get("VALICHEF_PRINTER_PORT", "9100"))
PRINTER_CONFIG_FILE = os.environ.get("VALICHEF_PRINTER_CONFIG_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".printer-config.json"))
try:
    if os.path.exists(PRINTER_CONFIG_FILE):
        with open(PRINTER_CONFIG_FILE, "r", encoding="utf-8") as arq:
            _pcfg = json.load(arq)
        PRINTER_HOST = str(_pcfg.get("host") or PRINTER_HOST)
        PRINTER_PORT = int(_pcfg.get("porta") or PRINTER_PORT)
        VALICHEF_IMPRESSORA_ID = str(_pcfg.get("impressora_id") or VALICHEF_IMPRESSORA_ID)
except Exception as erro:
    print(f"Nao foi possivel carregar configuracao local da impressora: {erro}")
INTERVALO_FILA_SEGUNDOS = max(0.25, float(os.environ.get("VALICHEF_QUEUE_INTERVAL", "0.25")))
CAMERA_SESSION_INTERVAL = max(0.25, float(os.environ.get("VALICHEF_CAMERA_SESSION_INTERVAL", "0.5")))
CAMERA_RTSP_PASSWORDS = {}
try:
    CAMERA_RTSP_PASSWORDS = json.loads(os.environ.get("VALICHEF_CAMERA_PASSWORDS_JSON", "{}") or "{}")
except Exception:
    CAMERA_RTSP_PASSWORDS = {}
CAMERA_PEERS = {}
ULTIMA_API_LATENCIA_MS = None
ULTIMA_IMPRESSAO_MS = None
ULTIMA_IMPRESSAO_EM = None




def configuracao_fila_completa():
    return all([
        VALICHEF_API_URL,
        VALICHEF_BRIDGE_SECRET,
        VALICHEF_RESTAURANTE_ID,
        VALICHEF_IMPRESSORA_ID,
    ])


def configuracao_impressora_completa():
    return bool(PRINTER_HOST and PRINTER_PORT)


def testar_socket_impressora(host=None, porta=None):
    host = host or PRINTER_HOST
    porta = int(porta or PRINTER_PORT)
    if not host:
        raise RuntimeError("Impressora ainda nao configurada.")
    with socket.create_connection((host, porta), timeout=3):
        return True


def imprimir_raw(conteudo):
    if not configuracao_impressora_completa():
        raise RuntimeError("Impressora ainda nao configurada no Bridge.")

    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    with socket.create_connection((PRINTER_HOST, PRINTER_PORT), timeout=10) as conexao:
        conexao.sendall(dados)


def requisicao_valichef(metodo, caminho, corpo=None, parametros=None):
    url = f"{VALICHEF_API_URL}{caminho}"
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)

    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    cabecalhos = {
        "Authorization": f"Bearer {VALICHEF_BRIDGE_SECRET}",
        "Content-Type": "application/json",
        "X-ValiChef-Bridge-Id": VALICHEF_BRIDGE_ID,
    }
    req = urllib.request.Request(url=url, data=dados, headers=cabecalhos, method=metodo)
    with urllib.request.urlopen(req, timeout=15) as resposta:
        conteudo = resposta.read().decode("utf-8")
        return json.loads(conteudo) if conteudo else {}


def enviar_heartbeat():
    global ULTIMA_API_LATENCIA_MS
    if not VALICHEF_API_URL or not VALICHEF_BRIDGE_SECRET or not VALICHEF_BRIDGE_ID:
        print("Heartbeat desativado: Bridge ainda nao ativado no ValiChef.")
        return
    while True:
        try:
            status_impressora = "nao_configurada"
            detalhe = None
            printer_latency_ms = None
            if configuracao_impressora_completa():
                try:
                    t0 = time.perf_counter()
                    testar_socket_impressora()
                    printer_latency_ms = int((time.perf_counter() - t0) * 1000)
                    status_impressora = "online"
                except Exception as erro:
                    status_impressora = "offline"
                    detalhe = str(erro)
            inicio_api = time.perf_counter()
            requisicao_valichef("POST", "/api/bridge/status", corpo={
                "bridge_id": VALICHEF_BRIDGE_ID,
                "restaurante_id": VALICHEF_RESTAURANTE_ID or None,
                "impressora_id": VALICHEF_IMPRESSORA_ID or None,
                "status": "online",
                "versao": BRIDGE_VERSION,
                "hostname": socket.gethostname(),
                "sistema_operacional": "linux",
                "impressora_status": status_impressora,
                "detalhe": detalhe,
                "api_latency_ms": ULTIMA_API_LATENCIA_MS,
                "printer_latency_ms": printer_latency_ms,
                "ultima_impressao_ms": ULTIMA_IMPRESSAO_MS,
                "ultima_impressao_em": ULTIMA_IMPRESSAO_EM,
                "fila_intervalo_ms": int(INTERVALO_FILA_SEGUNDOS * 1000),
            })
            ULTIMA_API_LATENCIA_MS = int((time.perf_counter() - inicio_api) * 1000)
        except Exception as erro:
            print(f"Erro no heartbeat: {erro}")
        time.sleep(max(HEARTBEAT_INTERVAL, 10))


def descobrir_impressoras_rede():
    """Procura impressoras RAW na mesma rede /24 sem alterar a configuracao atual."""
    alvo = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        alvo.connect(("8.8.8.8", 80))
        ip_local = alvo.getsockname()[0]
    finally:
        alvo.close()
    prefixo = ".".join(ip_local.split(".")[:3])
    encontrados = []
    def testar_ip(n):
        ip = f"{prefixo}.{n}"
        try:
            with socket.create_connection((ip, 9100), timeout=0.18):
                return {"ip": ip, "porta": 9100}
        except Exception:
            return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=48) as pool:
        for item in pool.map(testar_ip, range(1, 255)):
            if item:
                encontrados.append(item)
    return encontrados


def etiqueta_teste_valichef(codigo):
    # Etiqueta de diagnostico isolada. Nao altera o comando/layout das etiquetas normais.
    codigo = str(codigo or "IMPRESSORA").strip().upper()
    titulo = f"ValiChef-{codigo}"
    return (
        "^XA"
        "^PW480^LL480"
        "^FO35,145^A0N,42,42^FD" + titulo + "^FS"
        "^FO35,220^A0N,64,64^FDA T I V O^FS"
        "^FO35,310^A0N,24,24^FDTeste de comunicacao ValiChef^FS"
        "^XZ"
    )


def salvar_configuracao_impressora(impressora_id, host, porta=9100):
    global VALICHEF_IMPRESSORA_ID, PRINTER_HOST, PRINTER_PORT
    testar_socket_impressora(host, porta)
    dados = {"impressora_id": str(impressora_id), "host": str(host), "porta": int(porta)}
    tmp = PRINTER_CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as arq:
        json.dump(dados, arq)
    os.replace(tmp, PRINTER_CONFIG_FILE)
    VALICHEF_IMPRESSORA_ID = dados["impressora_id"]
    PRINTER_HOST = dados["host"]
    PRINTER_PORT = dados["porta"]


def executar_comando_remoto(comando):
    tipo = comando.get("tipo")
    parametros = comando.get("parametros") or {}
    if tipo == "testar_impressora":
        testar_socket_impressora()
        codigo = parametros.get("codigo_impressora") or VALICHEF_IMPRESSORA_ID or "IMPRESSORA"
        imprimir_raw(etiqueta_teste_valichef(codigo))
        return {"mensagem": f"Etiqueta de teste enviada para {codigo}."}
    if tipo == "procurar_impressoras":
        encontrados = descobrir_impressoras_rede()
        return {"mensagem": f"{len(encontrados)} impressora(s) encontrada(s) na rede.", "impressoras": encontrados}
    if tipo == "configurar_impressora":
        iid = parametros.get("impressora_id")
        host = parametros.get("ip")
        porta = int(parametros.get("porta") or 9100)
        if not iid or not host:
            raise RuntimeError("Dados da impressora incompletos.")
        salvar_configuracao_impressora(iid, host, porta)
        return {"mensagem": f"Impressora {parametros.get('codigo_impressora') or iid} vinculada ao Bridge."}
    if tipo == "diagnostico":
        printer = "nao_configurada"
        if configuracao_impressora_completa():
            try:
                testar_socket_impressora()
                printer = "online"
            except Exception as erro:
                printer = f"offline: {erro}"
        return {
            "hostname": socket.gethostname(),
            "versao": BRIDGE_VERSION,
            "impressora": printer,
            "fila_configurada": configuracao_fila_completa(),
        }
    if tipo == "sincronizar_configuracao":
        return {"mensagem": "Configuracao sincronizada; nenhuma alteracao pendente."}
    if tipo == "atualizar_bridge":
        raise RuntimeError("Atualizador seguro ainda nao instalado neste equipamento.")
    if tipo == "remote_exec":
        parametros = comando.get("parametros") or {}
        shell_cmd = str(parametros.get("command") or "").strip()
        if not shell_cmd:
            raise RuntimeError("Comando remoto vazio.")
        if len(shell_cmd) > 2000:
            raise RuntimeError("Comando remoto muito grande.")
        inicio = time.perf_counter()
        proc = subprocess.run(
            ["/bin/bash", "-lc", shell_cmd],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        duracao = int((time.perf_counter() - inicio) * 1000)
        stdout = (proc.stdout or "")[-12000:]
        stderr = (proc.stderr or "")[-12000:]
        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duracao_ms": duracao,
            "usuario": os.environ.get("USER") or "valichef",
            "hostname": socket.gethostname(),
        }
    if tipo == "reiniciar_bridge":
        return {"mensagem": "Bridge sera reiniciado."}
    raise RuntimeError("Comando remoto nao reconhecido.")


def processar_comandos_remotos():
    if not VALICHEF_API_URL or not VALICHEF_BRIDGE_SECRET or not VALICHEF_BRIDGE_ID:
        print("Controle remoto desativado: Bridge ainda nao ativado.")
        return
    print("Controle remoto seguro do ValiChef ativado.")
    while True:
        try:
            resposta = requisicao_valichef("GET", "/api/bridge/comandos")
            comando = resposta.get("comando")
            if comando:
                cid = comando.get("id")
                try:
                    resultado = executar_comando_remoto(comando)
                    requisicao_valichef("PATCH", "/api/bridge/comandos", corpo={"id": cid, "status": "concluido", "resultado": resultado})
                    if comando.get("tipo") == "reiniciar_bridge":
                        time.sleep(1)
                        os._exit(0)
                except Exception as erro:
                    requisicao_valichef("PATCH", "/api/bridge/comandos", corpo={"id": cid, "status": "erro", "erro": str(erro)})
        except Exception as erro:
            print(f"Erro no controle remoto: {erro}")
        time.sleep(10)


def buscar_sessao_camera():
    return requisicao_valichef("GET", "/api/bridge/cameras")


def responder_sessao_camera(sessao_id, status, answer_sdp=None, erro=None):
    corpo = {"id": sessao_id, "status": status}
    if answer_sdp is not None:
        corpo["answer_sdp"] = answer_sdp
    if erro is not None:
        corpo["erro"] = erro
    return requisicao_valichef("PATCH", "/api/bridge/cameras", corpo=corpo)


def montar_url_rtsp(camera):
    protocolo = str(camera.get("protocolo") or "rtsp").lower()
    if protocolo not in ("rtsp", "onvif"):
        raise RuntimeError("O gateway WebRTC requer uma câmera RTSP/ONVIF.")
    host = str(camera.get("endereco") or "").strip()
    if not host:
        raise RuntimeError("Câmera sem IP/endereço configurado.")
    porta = int(camera.get("porta") or 554)
    caminho = str(camera.get("caminho_stream") or "").strip()
    if caminho and not caminho.startswith("/"):
        caminho = "/" + caminho
    usuario = urllib.parse.quote(str(camera.get("usuario") or ""), safe="")
    senha = urllib.parse.quote(str(CAMERA_RTSP_PASSWORDS.get(str(camera.get("id")), "")), safe="")
    auth = ""
    if usuario:
        auth = usuario + ((":" + senha) if senha else "") + "@"
    return f"rtsp://{auth}{host}:{porta}{caminho}"


async def aguardar_ice(pc, limite=5.0):
    inicio = time.time()
    while pc.iceGatheringState != "complete" and time.time() - inicio < limite:
        await asyncio.sleep(0.05)


async def abrir_camera_webrtc(sessao):
    sid = str(sessao.get("id"))
    camera = sessao.get("camera") or {}
    if not sid or not sessao.get("offer_sdp"):
        raise RuntimeError("Sessão WebRTC inválida.")
    url = montar_url_rtsp(camera)
    pc = RTCPeerConnection()
    CAMERA_PEERS[sid] = pc

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            CAMERA_PEERS.pop(sid, None)

    try:
        player = MediaPlayer(url, format="rtsp", options={
            "rtsp_transport": "tcp",
            "stimeout": "3000000",
            "fflags": "nobuffer",
            "flags": "low_delay",
        })
        if not player.video:
            raise RuntimeError("A câmera não forneceu faixa de vídeo.")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sessao["offer_sdp"], type="offer"))
        pc.addTrack(player.video)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await aguardar_ice(pc)
        await asyncio.to_thread(responder_sessao_camera, sid, "pronta", pc.localDescription.sdp, None)
        print(f"Camera WebRTC {camera.get('id')} pronta na sessao {sid}.")
    except Exception:
        await pc.close()
        CAMERA_PEERS.pop(sid, None)
        raise


async def processar_cameras_webrtc_async():
    if not VALICHEF_API_URL or not VALICHEF_BRIDGE_SECRET or not VALICHEF_BRIDGE_ID:
        print("Gateway WebRTC desativado: Bridge ainda nao ativado.")
        return
    print("Gateway WebRTC de cameras ativado.")
    while True:
        try:
            resposta = await asyncio.to_thread(buscar_sessao_camera)
            sessao = resposta.get("sessao") if isinstance(resposta, dict) else None
            if sessao:
                try:
                    await abrir_camera_webrtc(sessao)
                    continue
                except Exception as erro:
                    print(f"Erro ao abrir camera WebRTC: {erro}")
                    try:
                        await asyncio.to_thread(responder_sessao_camera, sessao.get("id"), "erro", None, str(erro))
                    except Exception as erro_status:
                        print(f"Nao foi possivel registrar erro da camera: {erro_status}")
        except Exception as erro:
            print(f"Erro no gateway WebRTC: {erro}")
        await asyncio.sleep(CAMERA_SESSION_INTERVAL)


def processar_cameras_webrtc():
    asyncio.run(processar_cameras_webrtc_async())


def buscar_proximo_trabalho():
    return requisicao_valichef(
        "GET",
        "/api/bridge/fila",
        parametros={
            "restaurante_id": VALICHEF_RESTAURANTE_ID,
            "impressora_id": VALICHEF_IMPRESSORA_ID,
        },
    )


def concluir_trabalho(trabalho_id):
    return requisicao_valichef(
        "PATCH", "/api/bridge/fila",
        corpo={"id": trabalho_id, "status": "concluido"},
    )


def registrar_erro_trabalho(trabalho_id, mensagem):
    return requisicao_valichef(
        "PATCH", "/api/bridge/fila",
        corpo={"id": trabalho_id, "status": "erro", "erro": mensagem},
    )


def processar_fila():
    global ULTIMA_IMPRESSAO_MS, ULTIMA_IMPRESSAO_EM
    if not configuracao_fila_completa():
        print("Fila automatica desativada: faltam configuracoes do ValiChef.")
        return

    print("Fila automatica do ValiChef ativada.")
    while True:
        trabalho = None
        try:
            resposta = buscar_proximo_trabalho()
            trabalho = resposta.get("trabalho")
            if trabalho:
                trabalho_id = trabalho.get("id")
                comando = trabalho.get("comando")
                if not comando:
                    raise RuntimeError("Trabalho recebido sem comando de impressao.")
                inicio_impressao = time.perf_counter()
                imprimir_raw(comando)
                ULTIMA_IMPRESSAO_MS = int((time.perf_counter() - inicio_impressao) * 1000)
                ULTIMA_IMPRESSAO_EM = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                concluir_trabalho(trabalho_id)
                print(f"Impressao {trabalho_id} concluida em {ULTIMA_IMPRESSAO_MS} ms.")
                # Se houver mais etiquetas, busca a proxima imediatamente.
                continue
        except urllib.error.HTTPError as erro:
            mensagem = erro.read().decode("utf-8", errors="replace")
            print(f"Erro HTTP na fila: {erro.code} - {mensagem}")
        except Exception as erro:
            mensagem = str(erro)
            print(f"Erro ao processar fila: {mensagem}")
            if trabalho and trabalho.get("id"):
                try:
                    registrar_erro_trabalho(trabalho["id"], mensagem)
                except Exception as erro_status:
                    print(f"Nao foi possivel registrar o erro: {erro_status}")
        time.sleep(INTERVALO_FILA_SEGUNDOS)


@app.get("/")
def inicio():
    return jsonify({
        "servico": "ValiChef Bridge",
        "versao": BRIDGE_VERSION,
        "status": "online",
        "fila_configurada": configuracao_fila_completa(),
        "impressora_configurada": configuracao_impressora_completa(),
    })


@app.get("/impressora/status")
def status_impressora():
    if not configuracao_impressora_completa():
        return jsonify({
            "online": False,
            "configurada": False,
            "mensagem": "Impressora ainda nao configurada.",
        })
    try:
        testar_socket_impressora()
        return jsonify({
            "online": True,
            "configurada": True,
            "host": PRINTER_HOST,
            "porta": PRINTER_PORT,
        })
    except Exception as erro:
        return jsonify({
            "online": False,
            "configurada": True,
            "host": PRINTER_HOST,
            "porta": PRINTER_PORT,
            "mensagem": str(erro),
        }), 503


@app.get("/testar/<ip>/<int:porta>")
def testar_impressora(ip, porta):
    try:
        testar_socket_impressora(ip, porta)
        return jsonify({"online": True, "ip": ip, "porta": porta})
    except Exception as erro:
        return jsonify({"online": False, "ip": ip, "porta": porta, "mensagem": str(erro)}), 503


@app.post("/impressora/imprimir")
def imprimir():
    dados = request.get_json(silent=True) or {}
    comando = dados.get("comando") or dados.get("zpl")
    if not comando:
        return jsonify({"sucesso": False, "mensagem": "Nenhum comando foi enviado."}), 400
    try:
        imprimir_raw(comando)
        return jsonify({"sucesso": True, "mensagem": "Etiqueta enviada para a impressora."})
    except Exception as erro:
        return jsonify({"sucesso": False, "mensagem": str(erro)}), 500


if __name__ == "__main__":
    print(f"ValiChef Bridge {BRIDGE_VERSION} iniciado.")
    thread_heartbeat = threading.Thread(target=enviar_heartbeat, daemon=True)
    thread_heartbeat.start()
    thread_fila = threading.Thread(target=processar_fila, daemon=True)
    thread_fila.start()
    thread_remoto = threading.Thread(target=processar_comandos_remotos, daemon=True)
    thread_remoto.start()
    thread_cameras = threading.Thread(target=processar_cameras_webrtc, daemon=True)
    thread_cameras.start()
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)