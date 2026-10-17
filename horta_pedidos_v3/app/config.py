import os
from zoneinfo import ZoneInfo

APP_NAME = os.getenv('APP_NAME', 'Horta Pedidos')
SECRET_KEY = os.getenv('SECRET_KEY', 'troque-esta-chave-em-producao')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./horta.db')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000').rstrip('/')
APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'America/Sao_Paulo')
TZ = ZoneInfo(APP_TIMEZONE)
ORDER_CUTOFF_HOUR = int(os.getenv('ORDER_CUTOFF_HOUR', '22'))
COOKIE_SECURE = os.getenv('COOKIE_SECURE', '0') == '1'

ADMIN_NAME = os.getenv('ADMIN_NAME', 'Administrador')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@horta.local')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'TroqueEstaSenha123!')

SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'nao-responda@horta.local')
SMTP_TLS = os.getenv('SMTP_TLS', '1') == '1'
SHOW_RESET_LINK = os.getenv('SHOW_RESET_LINK', '0') == '1'

# WhatsApp Business Cloud API (opcional; necessário para envios automáticos)
WHATSAPP_API_BASE = os.getenv('WHATSAPP_API_BASE', 'https://graph.facebook.com').rstrip('/')
WHATSAPP_API_VERSION = os.getenv('WHATSAPP_API_VERSION', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_TEMPLATE_NAME = os.getenv('WHATSAPP_TEMPLATE_NAME', 'lembrete_pedido_horta')
WHATSAPP_TEMPLATE_LANG = os.getenv('WHATSAPP_TEMPLATE_LANG', 'pt_BR')
