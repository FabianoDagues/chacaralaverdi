# Horta Pedidos

## Versão 4.0

- Romaneio reorganizado para: **QTDE | UNIDADE | DESCRIÇÃO | PREÇO UNITÁRIO | TOTAL PRODUTO**.
- Impressão em duas vias (1ª e 2ª via) na mesma folha A4, com apenas um cliente/pedido por página.
- Disponibilidade em massa por período: selecione produtos e aplique/remova de uma data inicial até uma data final sem apagar os demais produtos já configurados.


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

## V3.6 — relatório operacional de colheita
- Dashboard com acesso direto a **Ver relatório para colher** e **Imprimir** junto aos totais por produto.
- Relatório A4 com total de cada produto para a data de entrega, fonte grande e campo de conferência.
- Impressão operacional do relatório liberada somente para pedidos do dia seguinte, seguindo a mesma proteção dos romaneios.
- Fontes de produtos e quantidades ampliadas nos romaneios para facilitar a leitura na separação/entrega.


## V3.8
- Romaneio com 54% da largura reservada ao produto.
- Produto em 20 px e quantidade em 19 px, usando Arial/Helvetica e peso 700 para leitura grande sem excesso de negrito.
- Preço/total compactados e alinhados à direita.
- Relatório de colheita com tipografia mais leve e ampliada.


## V3.9
- Nome fantasia do cliente ampliado nos romaneios.
- Tipografia dos produtos mais leve e legível.
- Impressões e relatórios internos passam a abrir na mesma guia para evitar acúmulo de abas.


## V4.1 — quantidade segura no pedido
- Botões − e + alteram a quantidade de 1 em 1.
- Ao clicar/tocar no número, o valor atual é selecionado para ser sobrescrito ao digitar.
- O campo aceita somente números inteiros e restaura 0 se for deixado vazio.


## V4.2
- Botões + e - do pedido alteram a quantidade sem focar o campo e sem abrir o teclado no celular.
- Teclado numérico abre somente ao tocar diretamente no campo para digitação manual.


## V4.3
- Romaneio em duas vias na mesma folha A4, sem quebra entre vias.
- Grade do romaneio com valores em fonte 18 normal; cabeçalhos e total em negrito.


## V4.4 — Romaneio adaptativo
- Até 10 itens: 1ª e 2ª via permanecem juntas na mesma folha A4.
- Acima de 10 itens: 1ª via ocupa uma página e 2ª via ocupa a página seguinte, mantendo fonte 18 e evitando cortes.
- Cada pedido começa em sua própria página e nunca é misturado com outro cliente.


## V4.5 - romaneio PDF
- Romaneios agora são gerados como PDF A4 no servidor, eliminando diferenças de paginação entre PC, Android e iPhone.
- Até 10 itens: 1ª e 2ª via na mesma folha. Pedidos maiores: vias em páginas separadas, sem corte de linhas.
