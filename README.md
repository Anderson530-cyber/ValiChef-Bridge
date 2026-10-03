# ValiChef Bridge

Pacote oficial do Bridge Linux/Ubuntu usado nos mini PCs dos restaurantes.

## Conteúdo

```
ValiChef-Bridge/
├── instalar-valichef-bridge.sh
├── valichef-bridge.service
└── valichef-bridge/
    ├── bridge.py
    ├── requirements.txt
    └── valichef-bridge.env.example
```

## Versão

Pacote preparado como **ValiChef Bridge 1.9.0**.

O código foi obtido do mini PC de teste. Durante a revisão foram corrigidas duas inconsistências do arquivo encontrado no equipamento: o código ainda declarava a versão 1.6.0 e a função de heartbeat existia, mas não era iniciada no bloco principal.

## Instalação em um mini PC novo

Depois de instalar o Ubuntu:

```bash
chmod +x instalar-valichef-bridge.sh
sudo ./instalar-valichef-bridge.sh
```

O instalador:

- instala Python, venv, pip e ffmpeg;
- cria o usuário `valichef` quando necessário;
- instala o Bridge em `/home/valichef/valichef-bridge`;
- recria o ambiente virtual;
- instala as dependências;
- instala e habilita o serviço `systemd`;
- impede suspensão/hibernação do mini PC;
- preserva uma configuração existente;
- cria `/etc/valichef-bridge.env` a partir do exemplo quando ainda não existe.

## Configuração/ativação

Os valores reais de ativação **não ficam no GitHub**. Eles ficam somente no mini PC em:

```
/etc/valichef-bridge.env
```

Depois de preencher os dados de ativação:

```bash
sudo systemctl restart valichef-bridge
```

## Verificar

```bash
systemctl status valichef-bridge --no-pager
```

Logs:

```bash
journalctl -u valichef-bridge -f
```

## Teste obrigatório antes de distribuição

1. Fechar o Terminal e confirmar que o Bridge continua online.
2. Imprimir uma etiqueta.
3. Reiniciar o Ubuntu e confirmar retorno automático.
4. Configurar a BIOS para **Power On / Restore on AC Power Loss**.
5. Simular queda de energia.
6. Confirmar que o mini PC liga sozinho.
7. Confirmar Bridge e impressora online no Admin 110 Tech sem abrir Terminal.
8. Imprimir novamente.
