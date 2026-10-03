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

A ativação agora é automática e segura. Os valores reais **não ficam no GitHub** e o segredo do Bridge não é exibido no Admin.

Ao executar o instalador em um mini PC novo, ele:

1. gera localmente uma credencial aleatória;
2. envia ao servidor somente o hash dessa credencial;
3. mostra um código temporário no formato `VC-XXXXXX`;
4. aguarda a confirmação no **Admin 110 Tech → Equipamentos → Ativar equipamento**;
5. depois da confirmação, recebe apenas os IDs e a configuração da impressora;
6. grava automaticamente:

```
/etc/valichef-bridge.env
```

O arquivo fica com permissão `600` e contém a credencial local necessária ao Bridge.

### Fluxo de implantação

```
Instalar Ubuntu
→ configurar BIOS
→ conectar à internet/rede do restaurante
→ executar instalar-valichef-bridge.sh
→ copiar o código VC-XXXXXX mostrado na tela
→ Admin 110 Tech > Equipamentos > Ativar equipamento
→ escolher restaurante + impressora
→ instalador conclui automaticamente
→ Bridge inicia pelo systemd
```

O código temporário expira em aproximadamente 30 minutos e um novo provisionamento invalida a tentativa pendente anterior do mesmo mini PC.

Se o equipamento já possuir uma configuração completa em `/etc/valichef-bridge.env`, o instalador preserva essa configuração e não exige nova ativação.

## Verificar

```bash
systemctl status valichef-bridge --no-pager
```

Logs:

```bash
journalctl -u valichef-bridge -f
```

## BIOS/energia — configuração obrigatória

O Bridge inicia automaticamente pelo `systemd`, mas o sistema operacional só consegue subir após uma queda de energia se o próprio mini PC estiver configurado para voltar a ligar quando a alimentação AC retornar.

No mini PC homologado durante o teste, foi necessário configurar **as duas opções abaixo**:

1. **Chipset → SoC Configuration → Restore AC Power Loss = Power On**
2. **Advanced → Power Management Setup → EuP Function = Disabled**

> Importante: somente `Restore AC Power Loss = Power On` não foi suficiente nesse equipamento. O auto power-on só funcionou depois que `EuP Function` foi alterado para `Disabled`.

Os nomes e caminhos podem variar conforme a BIOS/placa-mãe. Procure equivalentes como `AC Power Recovery`, `After Power Failure`, `State After G3`, `Restore on AC Power Loss` ou `ErP/EuP`.

Depois de alterar a BIOS, salve com **Save & Exit** e faça um teste físico real.

## Teste obrigatório antes de distribuição

1. Instalar o Bridge e confirmar `systemctl status valichef-bridge` como **active (running)**.
2. Fechar o Terminal e confirmar que o Bridge continua online no Admin 110 Tech.
3. Confirmar impressora online.
4. Imprimir uma etiqueta pela web.
5. Reiniciar o Ubuntu e, sem abrir Terminal, confirmar que Bridge e impressora voltaram online.
6. Imprimir novamente pela web.
7. Confirmar na BIOS:
   - **Restore AC Power Loss = Power On**
   - **EuP Function = Disabled** quando disponível/necessário.
8. Com o Ubuntu totalmente iniciado, cortar a energia do mini PC.
9. Aguardar pelo menos 10 segundos.
10. Restaurar a energia **sem apertar o botão Power**.
11. Confirmar que o mini PC liga sozinho.
12. Sem abrir Terminal, confirmar no Admin 110 Tech:
    - Bridge online;
    - versão esperada do Bridge;
    - impressora online.
13. Imprimir uma etiqueta pela web.
14. No APK Android, validar também a impressão direta com o Bridge temporariamente parado; após o teste, religar o serviço.

### Critério de homologação

O mini PC só deve ser considerado aprovado para instalação em cliente quando passar por este fluxo completo:

`energia cai → energia volta → mini PC liga sozinho → Ubuntu inicia → Bridge sobe pelo systemd → Admin mostra online → impressora fica online → impressão web funciona`.

A impressão direta pelo APK deve continuar funcionando como caminho independente da fila/Bridge.


## Acesso remoto pelo Admin 110 Tech

A partir do Bridge **1.10.0**, o mini PC pode receber comandos administrativos pelo mesmo canal autenticado que já processa diagnóstico e controle remoto.

Fluxo:

```
Admin 110 Tech
→ Equipamentos
→ selecionar o Bridge
→ Acesso remoto
→ Console remoto
→ comando entra em bridge_comandos
→ Bridge consulta a fila autenticada
→ comando é executado localmente
→ saída, erro, código de retorno e duração voltam ao Admin
```

Características de segurança:
- nenhuma porta SSH/RDP é aberta automaticamente na internet;
- o Bridge continua iniciando conexões de saída para o backend;
- o comando roda como o usuário do serviço `valichef`, não como `root`;
- execução limitada a 20 segundos por comando;
- stdout/stderr são limitados antes de serem enviados ao backend;
- os comandos ficam registrados em `bridge_comandos` para auditoria;
- ações privilegiadas do sistema devem continuar sendo implementadas como comandos específicos e controlados, em vez de liberar root permanente.

Atalhos do Admin incluem status do PC, status do serviço, últimos logs e informações de rede.
