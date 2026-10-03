# ValiChef Bridge

Pacote oficial de instalação do **ValiChef Bridge** para mini PCs Linux/Ubuntu usados nos restaurantes.

## Estrutura

```
VALICHEF-BRIDGE/
├── instalar-valichef-bridge.sh
├── valichef-bridge.service
├── README.md
└── valichef-bridge/
    ├── config.example
    └── README.md
```

## Objetivo

Após a instalação, o Bridge deve:

- iniciar automaticamente com o Ubuntu;
- continuar funcionando sem Terminal aberto;
- reiniciar automaticamente se o processo falhar;
- voltar sozinho após reinicialização ou queda de energia, desde que a BIOS esteja configurada para ligar após retorno da energia;
- manter a comunicação com o Admin 110 Tech;
- operar como fallback de impressão quando necessário.

## Instalação no mini PC

1. Baixe este repositório como ZIP no GitHub.
2. Extraia a pasta para o pendrive.
3. No mini PC com Ubuntu, abra a pasta pelo Terminal.
4. Execute:

```bash
chmod +x instalar-valichef-bridge.sh
sudo ./instalar-valichef-bridge.sh
```

O instalador copia os arquivos para `/opt/valichef/bridge`, instala o serviço `systemd` e o habilita para iniciar no boot.

## Verificar status

```bash
systemctl status valichef-bridge --no-pager
```

## Ver logs

```bash
journalctl -u valichef-bridge -f
```

## Reiniciar o Bridge

```bash
sudo systemctl restart valichef-bridge
```

## Importante

O diretório `valichef-bridge/` precisa conter os **arquivos reais da versão do Bridge que será instalada**. Não coloque chaves, tokens ou senhas diretamente neste repositório. Dados de ativação devem ficar no mini PC, fora do GitHub.

A primeira versão que vamos validar é a **1.9.0** atualmente usada no mini PC de teste. Depois do teste real, o pacote poderá ser versionado para distribuição.
