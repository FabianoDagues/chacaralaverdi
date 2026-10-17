# Status do projeto - Horta Pedidos

## Implementado e validado
- Cadastro da empresa e logo armazenada no PostgreSQL.
- Vínculo de empresa em produtos, clientes, operadores, disponibilidade, pedidos, contas a receber, recibos e lembretes.
- CRUD de produtos.
- CRUD de clientes, com bloqueio manual/financeiro e opção individual de lembrete.
- CRUD de operadores.
- Login de operador e login de cliente.
- Recuperação de senha do cliente por token temporário.
- Disponibilidade de produtos por dia, preço do dia e limite de quantidade.
- Pedido do cliente para o próximo dia, com controle de horário de corte.
- Dashboard administrativo com pedidos, clientes sem pedido, totais por produto, valores e gráfico.
- Lembrete manual por WhatsApp.
- Configuração de lembrete automático: ativar/desativar, horário, número de tentativas e intervalo.
- Worker interno para envio automático pela WhatsApp Business Cloud API quando as credenciais estiverem configuradas.
- Romaneio individual e em lote, com logo e dados da empresa.
- Contas a receber por cliente.
- Relatório de contas em aberto por cliente ordenado por vencimento.
- Baixa individual com recibo.
- Baixa de todos os títulos em aberto do cliente em uma única operação e um único recibo consolidado.
- Histórico/reimpressão de recibos.
- Relatórios de vendas, inadimplentes, mais vendidos e diagnóstico.
- PWA responsiva para desktop, Android e iOS.

## Integrações externas que dependem de credenciais
- Envio de e-mail para “Esqueci minha senha”: requer SMTP.
- Disparo automático de WhatsApp: requer conta/API oficial WhatsApp Business Cloud e template aprovado.

## Validação técnica
Foi executado um teste ponta a ponta em banco SQLite limpo cobrindo: empresa/logo, produto, cliente, operador, disponibilidade, pedido, dashboard, contas a receber, baixa total, recibo consolidado, romaneio e relatórios.


## Ajuste de quantidade
- Quantidade do pedido em passos inteiros: 0,000 → 1,000 → 2,000.

## V3.3 — fluxo de conclusão do pedido
- Login do cliente não cria pedido vazio; o registro só nasce ao clicar em Enviar pedido.
- Confirmação visual destacada após envio com número, entrega e total.
- Relatório do pedido para consulta/impressão pelo cliente.
- Cliente pode editar o pedido do próximo dia enquanto o prazo estiver aberto.
- Cliente pode excluir o pedido enquanto o prazo estiver aberto e sem pagamento registrado.
- Histórico ganhou ações Ver/imprimir e Editar quando permitido.


## V3.4 — preparação para produção e autocadastro
- Rotina administrativa **Limpar movimentação de testes**, protegida por frase de confirmação, senha do administrador e alerta irreversível.
- Limpeza remove clientes de teste, disponibilidades, pedidos, contas a receber, recibos, tokens de senha e logs de lembrete; preserva empresa/logo, produtos, operadores e configurações.
- Autocadastro opcional de clientes com senha/código provisório definido pela horta.
- Cliente preenche os próprios dados, cria senha definitiva e pode ser liberado imediatamente ou ficar aguardando aprovação do operador.
- Login informa quando o cadastro existe mas ainda não foi liberado.
