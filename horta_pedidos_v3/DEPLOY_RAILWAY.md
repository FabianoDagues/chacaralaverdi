# Implantação no Railway

## 1. Projeto separado
Crie um projeto Railway novo para a Horta. Não reutilize o projeto do sistema de cotações.

## 2. PostgreSQL
No projeto: **Add / New → Database → PostgreSQL**.

## 3. GitHub
Crie um repositório novo, por exemplo `horta-pedidos`, e envie o conteúdo desta pasta na raiz. `Dockerfile`, `requirements.txt` e `app/` devem ficar na raiz do repositório.

## 4. Aplicação
No Railway: **Add → GitHub Repo → selecione o repositório**.

## 5. Variáveis mínimas
No serviço da aplicação:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
SECRET_KEY=COLOQUE_UMA_CHAVE_LONGA_ALEATORIA
ADMIN_NAME=Administrador
ADMIN_EMAIL=seuemail@empresa.com.br
ADMIN_PASSWORD=UMA_SENHA_FORTE
COOKIE_SECURE=1
APP_TIMEZONE=America/Sao_Paulo
ORDER_CUTOFF_HOUR=22
PUBLIC_BASE_URL=https://ENDERECO-QUE-O-RAILWAY-GERAR.up.railway.app
```

`ORDER_CUTOFF_HOUR=22` permite pedidos para o dia seguinte até 21:59.

## 6. Domínio
Depois que o deploy ficar `Success`, gere um domínio em **Networking** e atualize `PUBLIC_BASE_URL` com ele.

## 7. Cadastro da empresa e logo
No primeiro login, acesse **Empresa**. Preencha os dados e envie a logo. A imagem fica no PostgreSQL, então não depende de volume de disco no Railway.

## 8. Recuperação de senha por e-mail (opcional)

```text
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_TLS=1
```

Para teste sem SMTP, `SHOW_RESET_LINK=1` mostra o link temporário na tela. Em produção, use `0`.

## 9. WhatsApp automático (opcional)
O lembrete manual funciona sem API. Para disparo automático, configure a API oficial WhatsApp Business Cloud:

```text
WHATSAPP_API_BASE=https://graph.facebook.com
WHATSAPP_API_VERSION=vXX.X
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_TEMPLATE_NAME=lembrete_pedido_horta
WHATSAPP_TEMPLATE_LANG=pt_BR
```

O template aprovado deve receber 3 parâmetros no corpo: nome do cliente, data do pedido e link para login.

## 10. Backup
Antes do uso definitivo, habilite a política de backup/snapshot compatível com o plano PostgreSQL escolhido no Railway.
