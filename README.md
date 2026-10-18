# Horta Pedidos

Sistema web responsivo para pedidos diários de uma horta, preparado para Railway + PostgreSQL e uso 24 horas.

## Módulos incluídos

- **Empresa:** cadastro de razão social, nome fantasia, CNPJ/CPF, contato, endereço e logo. A logo fica armazenada no banco PostgreSQL para não se perder em novos deploys. Produtos, clientes, operadores, pedidos, disponibilidade, contas a receber, recibos e lembretes ficam vinculados à empresa.
- **Produtos:** CRUD completo, categoria, unidade, preço padrão e ativação/desativação.
- **Disponibilidade diária:** o operador escolhe quais produtos estarão disponíveis para o dia seguinte, podendo definir preço do dia e limite de quantidade.
- **Clientes:** CRUD completo, login próprio, prazo de pagamento, limite de crédito, bloqueio manual, bloqueio automático por inadimplência e opção individual para receber ou não lembrete automático.
- **Operadores/usuários:** CRUD completo e login administrativo com acesso a todo o sistema.
- **Recuperação de senha do cliente:** token temporário de 1 hora; envio por e-mail quando SMTP estiver configurado.
- **Pedidos:** somente produtos liberados para o próximo dia; um pedido por cliente/data, editável até o horário de corte. Controle opcional de estoque total do dia.
- **Dashboard:** pedidos do próximo dia por cliente, clientes que não pediram, lembrete manual por WhatsApp, status do lembrete automático, total previsto, ticket médio, totais por produto e gráfico de pizza.
- **Romaneios:** impressão individual ou de todos os pedidos, com logo/dados da empresa, dados do cliente, produto, quantidade, preço unitário e total. Layout pensado para dois romaneios por folha A4 quando o conteúdo couber.
- **Contas a receber:** geradas automaticamente a partir do pedido, com vencimento, valor, saldo, status e bloqueio de pedidos quando houver inadimplência.
- **Contas em aberto por cliente:** visão consolidada ordenada por vencimento. Pode baixar um título individual ou todos os títulos em aberto do cliente de uma só vez.
- **Recibos:** toda baixa gera recibo. Na baixa de vários títulos, o sistema gera **um único recibo consolidado**, listando todos os pedidos/títulos quitados. Histórico permite reabrir e reimprimir.
- **Lembretes automáticos de pedido:** horário do primeiro aviso, quantidade máxima de tentativas, intervalo entre avisos e ativação individual por cliente. O disparo automático usa a API oficial do WhatsApp Business Cloud quando configurada. O link manual de WhatsApp funciona sem API.
- **Relatórios:** vendas por produto e cliente em período, inadimplentes, produtos mais vendidos e diagnóstico geral com faturamento, ticket médio, contas em aberto, clientes sem compra e evolução diária.
- **PWA:** instalável no desktop e Android; no iPhone/iPad pode ser adicionado à Tela de Início. Uma única aplicação atende computador, Android e iOS.
- **Responsivo:** telas adaptadas para desktop e celular.

## Railway

Crie um projeto Railway separado do sistema de cotações, adicione PostgreSQL e conecte este projeto via GitHub. Variáveis mínimas:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
SECRET_KEY=<chave longa aleatória>
ADMIN_NAME=Administrador
ADMIN_EMAIL=seuemail@empresa.com.br
ADMIN_PASSWORD=<senha forte>
PUBLIC_BASE_URL=https://seu-dominio.up.railway.app
COOKIE_SECURE=1
APP_TIMEZONE=America/Sao_Paulo
ORDER_CUTOFF_HOUR=22
```

O primeiro administrador e o primeiro cadastro de empresa são criados automaticamente. Depois do primeiro login, abra **Empresa** e preencha os dados e a logo.

## WhatsApp automático

O botão manual do Dashboard abre o WhatsApp com a mensagem pronta e não exige API. Para envio automático em horários programados, é necessário configurar a WhatsApp Business Cloud API e um template aprovado. As variáveis estão em `.env.example`.

## Observação sobre “contas a receber por fornecedor”

Como quem compra da horta é o cliente, o módulo financeiro foi implementado como **Contas a Receber por Cliente**, vinculado aos pedidos. Caso a horta compre produtos de terceiros, um módulo separado de **Contas a Pagar por Fornecedor** pode ser adicionado depois.


## Autocadastro de clientes

Em **Empresa**, o administrador pode ativar o autocadastro e definir uma senha/código provisório. O cliente acessa **Primeiro acesso / Fazer meu cadastro**, informa esse código, preenche seus dados e cria a própria senha. Opcionalmente, o administrador pode exigir aprovação antes do primeiro pedido.

## Limpeza da base de testes

Administradores têm a tela **Manutenção** para apagar movimentações de teste antes da entrega. A operação exige digitar `ZERAR BANCO`, informar novamente a senha do administrador e confirmar o alerta. São apagados clientes de teste, disponibilidades, pedidos, contas a receber, recibos, tokens de senha e histórico de lembretes. São preservados empresa/logo, produtos, operadores/usuários e configurações.

## V3.5 — Menu lateral e segurança de impressão

- Menu principal substituído por menu lateral responsivo.
- Em telas pequenas, o menu abre por botão hambúrguer e fecha por toque fora ou tecla Esc.
- Romaneios administrativos só podem ser impressos para a data de entrega do dia seguinte.
- Consultas históricas e outras datas continuam disponíveis, mas sem impressão.
- A restrição de impressão é validada também no servidor para evitar acesso direto por URL.
