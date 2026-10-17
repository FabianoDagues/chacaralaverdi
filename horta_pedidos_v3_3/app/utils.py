import re
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from .config import TZ

def now_local():
    return datetime.now(TZ)

def today_local():
    return now_local().date()

def tomorrow_local():
    return today_local() + timedelta(days=1)

def parse_decimal(value, default=Decimal('0')):
    if value is None or value == '':
        return default
    try:
        return Decimal(str(value).replace('.', '').replace(',', '.')) if ',' in str(value) else Decimal(str(value))
    except InvalidOperation:
        return default

def brl(value):
    try:
        v = Decimal(value or 0)
    except Exception:
        v = Decimal('0')
    s = f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}'

def qty(value):
    try:
        v = Decimal(value or 0)
    except Exception:
        return '0'
    if v == v.to_integral():
        return str(int(v))
    return f'{v:.3f}'.rstrip('0').rstrip('.').replace('.', ',')

def clean_whatsapp(value: str | None):
    if not value:
        return ''
    digits = re.sub(r'\D','', value)
    if len(digits) in (10,11):
        digits = '55' + digits
    return digits

def whatsapp_link(number: str | None, message: str):
    digits = clean_whatsapp(number)
    if not digits:
        return None
    return f'https://wa.me/{digits}?text={quote(message)}'
