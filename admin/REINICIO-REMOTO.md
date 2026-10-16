# Reinício remoto do mini PC (pré-produção)

Este recurso está numa branch de desenvolvimento e **não foi instalado no mini PC**.

1. Validar no backend que somente administradores autorizados da 110 Tech podem criar o tipo `reiniciar_mini_pc`, vinculado ao Bridge correto. Exigir confirmação explícita e registrar auditoria.
2. Verificar ausência de impressões pendentes e combinar janela de manutenção.
3. Revisar o helper e executar manualmente `sudo bash admin/instalar-reinicio-remoto.sh` no mini PC de testes. Não colocar instalação automática em atualizações existentes.
4. Com o Bridge atualizado e o backend autorizando o novo tipo, testar a solicitação pelo painel; conferir que o retorno é registrado e o Ubuntu reinicia após ~15 segundos.
5. Confirmar que Bridge e impressora voltam online, e que impressão de etiqueta funciona.
6. Testar rejeição de comandos por usuários sem permissão, comando duplicado e equipamento offline.

A execução usa `sudo -n` para um **único script root-owned**, sem conceder sudo geral ao usuário valichef. O script agenda reboot com systemd-run, evitando interromper a resposta HTTP imediatamente. A funcionalidade requer systemd-run disponível. Não exponha `remote_exec` a usuários comuns.

**Importante:** esta branch ainda não altera o Admin 110 Tech nem o backend; sem integração do botão e da autorização no servidor, o comando não estará disponível ao usuário.
