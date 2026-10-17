from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import smtplib
import asyncio
import json
import urllib.request
import urllib.error
from email.message import EmailMessage
from pathlib import Path

from fastapi import FastAPI, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, or_, text, inspect
from sqlalchemy.exc import IntegrityError

from .config import (
    APP_NAME, SECRET_KEY, COOKIE_SECURE, ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD,
    PUBLIC_BASE_URL, ORDER_CUTOFF_HOUR, SMTP_HOST, SMTP_PORT, SMTP_USER,
    SMTP_PASSWORD, SMTP_FROM, SMTP_TLS, SHOW_RESET_LINK, TZ,
    WHATSAPP_API_BASE, WHATSAPP_API_VERSION, WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_ACCESS_TOKEN, WHATSAPP_TEMPLATE_NAME, WHATSAPP_TEMPLATE_LANG
)
from .db import Base, engine, SessionLocal, get_db
from .models import (Company, User, Product, Client, Availability, Order, OrderItem, Receivable, PasswordResetToken,
    Receipt, ReceiptItem, ReminderSettings, ReminderLog)
from .security import hash_password, verify_password, generate_reset_token, hash_token
from .utils import now_local, today_local, tomorrow_local, brl, qty, parse_decimal, whatsapp_link

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title=APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=COOKIE_SECURE, same_site='lax')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))
templates.env.filters['brl'] = brl
templates.env.filters['qty'] = qty

def parse_date(value: str | None, default: date | None = None):
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def flash(request: Request, message: str, kind: str = 'success'):
    request.session['flash'] = {'message': message, 'kind': kind}


def base_context(request: Request, **kwargs):
    ctx = {
        'request': request,
        'app_name': APP_NAME,
        'operator': None,
        'client_session': None,
        'company': None,
        'flash': request.session.pop('flash', None),
        'today': today_local(),
        'tomorrow': tomorrow_local(),
    }
    ctx.update(kwargs)
    if not ctx.get('company'):
        actor = ctx.get('operator') or ctx.get('client_session') or ctx.get('client')
        ctx['company'] = getattr(actor, 'company', None) if actor else None
    return ctx


def current_operator(request: Request, db: Session):
    uid = request.session.get('operator_id')
    if not uid:
        return None
    return db.get(User, uid)


def current_client(request: Request, db: Session):
    cid = request.session.get('client_id')
    if not cid:
        return None
    return db.get(Client, cid)


def require_operator(request: Request, db: Session):
    user = current_operator(request, db)
    if not user or not user.is_active:
        return None
    return user


def require_client(request: Request, db: Session):
    client = current_client(request, db)
    if not client or not client.is_active:
        return None
    return client


def receivable_outstanding(r: Receivable):
    return max(Decimal(r.amount or 0) - Decimal(r.amount_paid or 0), Decimal('0'))


def update_receivable_status(r: Receivable):
    outstanding = receivable_outstanding(r)
    if outstanding <= 0:
        r.status = 'PAGO'
        if not r.paid_at:
            r.paid_at = datetime.utcnow()
    elif Decimal(r.amount_paid or 0) > 0:
        r.status = 'PARCIAL'
        r.paid_at = None
    elif r.due_date < today_local():
        r.status = 'VENCIDO'
        r.paid_at = None
    else:
        r.status = 'PENDENTE'
        r.paid_at = None


def client_block_reason(db: Session, client: Client):
    if client.manual_blocked:
        return client.blocked_reason or 'Cliente bloqueado manualmente.'
    recs = db.scalars(select(Receivable).where(Receivable.client_id == client.id)).all()
    outstanding_total = Decimal('0')
    for r in recs:
        update_receivable_status(r)
        out = receivable_outstanding(r)
        outstanding_total += out
        if out > 0 and r.due_date < today_local():
            return f'Cliente possui título vencido desde {r.due_date.strftime("%d/%m/%Y")}.'
    if client.credit_limit is not None and Decimal(client.credit_limit) > 0 and outstanding_total >= Decimal(client.credit_limit):
        return 'Limite de crédito atingido.'
    return None


def order_open_for(delivery_date: date):
    now = now_local()
    if delivery_date != tomorrow_local():
        return False
    return now.hour < ORDER_CUTOFF_HOUR


def send_reset_email(to_email: str, reset_url: str):
    if not SMTP_HOST:
        return False
    msg = EmailMessage()
    msg['Subject'] = f'{APP_NAME} - Redefinição de senha'
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    msg.set_content(
        f'Você solicitou uma nova senha para o {APP_NAME}.\n\n'
        f'Acesse este link (válido por 1 hora):\n{reset_url}\n\n'
        'Se você não solicitou, ignore esta mensagem.'
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        if SMTP_TLS:
            server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    return True



def ensure_schema_updates():
    """Small in-place migrations for existing Railway databases."""
    inspector = inspect(engine)
    if 'clients' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('clients')}
        if 'reminder_enabled' not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE clients ADD COLUMN reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE"))


def get_reminder_settings(db: Session, company_id: int = 1):
    settings = db.scalar(select(ReminderSettings).where(ReminderSettings.company_id == company_id))
    if not settings:
        settings = ReminderSettings(company_id=company_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def whatsapp_api_ready():
    return all([
        WHATSAPP_API_BASE, WHATSAPP_API_VERSION, WHATSAPP_PHONE_NUMBER_ID,
        WHATSAPP_ACCESS_TOKEN, WHATSAPP_TEMPLATE_NAME, WHATSAPP_TEMPLATE_LANG,
    ])


def normalize_whatsapp_number(value: str | None):
    digits = ''.join(ch for ch in (value or '') if ch.isdigit())
    if len(digits) in (10, 11):
        digits = '55' + digits
    return digits


def reminder_message(settings: ReminderSettings, client: Client, target_date: date):
    template = settings.manual_message or 'Olá, {nome}! Ainda não recebemos seu pedido para {data}. Faça seu pedido aqui: {link}'
    values = {
        'nome': client.trade_name or client.company_name,
        'data': target_date.strftime('%d/%m/%Y'),
        'link': f'{PUBLIC_BASE_URL}/cliente/login',
    }
    try:
        return template.format(**values)
    except Exception:
        return f"Olá, {values['nome']}! Ainda não recebemos seu pedido para {values['data']}. Faça seu pedido aqui: {values['link']}"


def send_whatsapp_template(client: Client, target_date: date):
    """Send an approved WhatsApp Business template with 3 body parameters: nome, data, link."""
    if not whatsapp_api_ready():
        raise RuntimeError('API oficial do WhatsApp ainda não configurada.')
    to = normalize_whatsapp_number(client.whatsapp or client.phone)
    if not to:
        raise RuntimeError('Cliente sem número de WhatsApp válido.')
    url = f"{WHATSAPP_API_BASE}/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'template',
        'template': {
            'name': WHATSAPP_TEMPLATE_NAME,
            'language': {'code': WHATSAPP_TEMPLATE_LANG},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': client.trade_name or client.company_name},
                    {'type': 'text', 'text': target_date.strftime('%d/%m/%Y')},
                    {'type': 'text', 'text': f'{PUBLIC_BASE_URL}/cliente/login'},
                ],
            }],
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'WhatsApp API HTTP {exc.code}: {detail[:300]}') from exc


def create_receipt(db: Session, client: Client, operator: User | None, allocations, payment_method: str = '', notes: str = ''):
    """allocations: iterable of (Receivable, amount). Updates balances and creates printable receipt."""
    clean = []
    total = Decimal('0')
    for r, amount in allocations:
        remaining = receivable_outstanding(r)
        value = min(Decimal(amount or 0), remaining)
        if value <= 0:
            continue
        clean.append((r, value))
        total += value
    if total <= 0:
        return None
    receipt = Receipt(
        company_id=client.company_id, number='TEMP', client_id=client.id, operator_id=operator.id if operator else None,
        payment_date=today_local(), total=total,
        payment_method=(payment_method or '').strip() or 'Não informado',
        notes=(notes or '').strip() or None,
    )
    db.add(receipt)
    db.flush()
    receipt.number = f'REC-{today_local().strftime("%Y%m%d")}-{receipt.id:06d}'
    for r, value in clean:
        r.amount_paid = min(Decimal(r.amount_paid or 0) + value, Decimal(r.amount or 0))
        if notes.strip():
            r.notes = notes.strip()
        update_receivable_status(r)
        db.add(ReceiptItem(
            receipt_id=receipt.id, receivable_id=r.id,
            order_number=r.order.number if r.order else str(r.order_id),
            order_date=(r.order.delivery_date if r.order else r.created_at.date()),
            due_date=r.due_date, amount=value,
        ))
    db.commit()
    db.refresh(receipt)
    return receipt


def localize_utc_naive(dt: datetime):
    return dt.replace(tzinfo=timezone.utc).astimezone(TZ)


def process_automatic_reminders_once():
    db = SessionLocal()
    try:
        settings_rows = db.scalars(select(ReminderSettings).where(ReminderSettings.enabled == True)).all()
        if not settings_rows or not whatsapp_api_ready():
            return
        now = now_local()
        target_date = tomorrow_local()
        for settings in settings_rows:
            try:
                hour, minute = [int(x) for x in settings.send_time.split(':', 1)]
            except Exception:
                hour, minute = 17, 0
            first_due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now < first_due:
                continue
            clients = db.scalars(select(Client).where(
                Client.company_id == settings.company_id,
                Client.is_active == True,
                Client.reminder_enabled == True,
            ).order_by(Client.company_name)).all()
            for client in clients:
                has_order = db.scalar(select(func.count(Order.id)).where(
                    Order.company_id == settings.company_id,
                    Order.client_id == client.id,
                    Order.delivery_date == target_date,
                    Order.status == 'SUBMITTED',
                )) or 0
                if has_order or client_block_reason(db, client):
                    continue
                last = db.scalar(select(ReminderLog).where(
                    ReminderLog.company_id == settings.company_id,
                    ReminderLog.client_id == client.id,
                    ReminderLog.target_date == target_date,
                ).order_by(ReminderLog.attempt_no.desc()).limit(1))
                attempt_no = (last.attempt_no + 1) if last else 1
                if attempt_no > max(1, int(settings.max_attempts or 1)):
                    continue
                due = (localize_utc_naive(last.sent_at) + timedelta(minutes=max(1, int(settings.interval_minutes or 1)))) if last else first_due
                if now < due:
                    continue
                log = ReminderLog(company_id=settings.company_id, client_id=client.id, target_date=target_date, attempt_no=attempt_no, status='PROCESSANDO')
                db.add(log)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    continue
                try:
                    send_whatsapp_template(client, target_date)
                    log.status = 'ENVIADO'
                    log.error = None
                except Exception as exc:
                    log.status = 'ERRO'
                    log.error = str(exc)[:500]
                log.sent_at = datetime.utcnow()
                db.commit()
    finally:
        db.close()


async def reminder_worker():
    while True:
        try:
            await asyncio.to_thread(process_automatic_reminders_once)
        except Exception:
            pass
        await asyncio.sleep(60)


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    db = SessionLocal()
    try:
        company = db.get(Company, 1)
        if not company:
            company = Company(id=1, legal_name='Minha Horta', trade_name='Minha Horta')
            db.add(company)
            db.commit()
        admin = db.scalar(select(User).where(func.lower(User.email) == ADMIN_EMAIL.lower()))
        if not admin:
            db.add(User(company_id=company.id, name=ADMIN_NAME, email=ADMIN_EMAIL.lower(), password_hash=hash_password(ADMIN_PASSWORD), role='ADMIN'))
            db.commit()
        get_reminder_settings(db, company.id)
    finally:
        db.close()


@app.on_event('startup')
async def startup_reminder_worker():
    app.state.reminder_task = asyncio.create_task(reminder_worker())


@app.on_event('shutdown')
async def shutdown_reminder_worker():
    task = getattr(app.state, 'reminder_task', None)
    if task:
        task.cancel()


@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(BASE_DIR / 'static' / 'manifest.webmanifest', media_type='application/manifest+json')


@app.get('/service-worker.js')
def service_worker():
    response = FileResponse(BASE_DIR / 'static' / 'service-worker.js', media_type='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response


@app.get('/')
def home(request: Request, db: Session = Depends(get_db)):
    if require_operator(request, db):
        return RedirectResponse('/admin', 303)
    if require_client(request, db):
        return RedirectResponse('/cliente/pedido', 303)
    return templates.TemplateResponse('home.html', base_context(request, company=db.get(Company,1)))

# ------------------------ LOGIN OPERADOR ------------------------
@app.get('/login')
def operator_login_get(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse('operator_login.html', base_context(request, company=db.get(Company,1)))


@app.post('/login')
def operator_login_post(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        flash(request, 'E-mail ou senha inválidos.', 'error')
        return RedirectResponse('/login', 303)
    request.session.clear()
    request.session['operator_id'] = user.id
    return RedirectResponse('/admin', 303)


@app.get('/logout')
def operator_logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', 303)

# ------------------------ LOGIN CLIENTE ------------------------
@app.get('/cliente/login')
def client_login_get(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse('client_login.html', base_context(request, company=db.get(Company,1)))


@app.post('/cliente/login')
def client_login_post(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    client = db.scalar(select(Client).where(func.lower(Client.email) == email.strip().lower()))
    if not client or not client.is_active or not verify_password(password, client.password_hash):
        flash(request, 'E-mail ou senha inválidos.', 'error')
        return RedirectResponse('/cliente/login', 303)
    request.session.clear()
    request.session['client_id'] = client.id
    return RedirectResponse('/cliente/pedido', 303)


@app.get('/cliente/logout')
def client_logout(request: Request):
    request.session.clear()
    return RedirectResponse('/cliente/login', 303)


@app.get('/cliente/esqueci-senha')
def forgot_get(request: Request):
    return templates.TemplateResponse('forgot_password.html', base_context(request))


@app.post('/cliente/esqueci-senha')
def forgot_post(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    client = db.scalar(select(Client).where(func.lower(Client.email) == email.strip().lower()))
    dev_link = None
    if client and client.is_active:
        raw, hashed, expires = generate_reset_token()
        db.query(PasswordResetToken).filter(PasswordResetToken.client_id == client.id, PasswordResetToken.used_at.is_(None)).delete()
        db.add(PasswordResetToken(company_id=client.company_id, client_id=client.id, token_hash=hashed, expires_at=expires))
        db.commit()
        reset_url = f'{PUBLIC_BASE_URL}/cliente/redefinir-senha?token={raw}'
        try:
            sent = send_reset_email(client.email, reset_url)
        except Exception:
            sent = False
        if SHOW_RESET_LINK and not sent:
            dev_link = reset_url
    return templates.TemplateResponse('forgot_password.html', base_context(
        request,
        sent_message='Se o e-mail estiver cadastrado, as instruções de redefinição foram geradas.',
        dev_link=dev_link
    ))


@app.get('/cliente/redefinir-senha')
def reset_get(request: Request, token: str, db: Session = Depends(get_db)):
    rt = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    valid = bool(rt and not rt.used_at and rt.expires_at >= datetime.utcnow())
    return templates.TemplateResponse('reset_password.html', base_context(request, token=token, valid=valid))


@app.post('/cliente/redefinir-senha')
def reset_post(request: Request, token: str = Form(...), password: str = Form(...), password2: str = Form(...), db: Session = Depends(get_db)):
    rt = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if not rt or rt.used_at or rt.expires_at < datetime.utcnow():
        flash(request, 'Link inválido ou expirado.', 'error')
        return RedirectResponse('/cliente/esqueci-senha', 303)
    if len(password) < 8 or password != password2:
        return templates.TemplateResponse('reset_password.html', base_context(request, token=token, valid=True, error='As senhas precisam ser iguais e ter no mínimo 8 caracteres.'))
    client = db.get(Client, rt.client_id)
    client.password_hash = hash_password(password)
    rt.used_at = datetime.utcnow()
    db.commit()
    flash(request, 'Senha alterada. Faça seu login.', 'success')
    return RedirectResponse('/cliente/login', 303)


# ------------------------ EMPRESA ------------------------
@app.get('/empresa/logo')
def company_logo(db: Session = Depends(get_db)):
    company = db.get(Company, 1)
    if not company or not company.logo_data:
        raise HTTPException(404)
    return Response(content=company.logo_data, media_type=company.logo_content_type or 'image/png', headers={'Cache-Control': 'public, max-age=3600'})


@app.get('/admin/empresa')
def company_get(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    company = db.get(Company, operator.company_id)
    if not company:
        raise HTTPException(404)
    return templates.TemplateResponse('company_form.html', base_context(request, operator=operator, company=company))


@app.post('/admin/empresa')
async def company_post(request: Request, logo: UploadFile | None = File(None), db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    company = db.get(Company, operator.company_id)
    if not company:
        raise HTTPException(404)
    form = await request.form()
    company.legal_name = (form.get('legal_name') or '').strip() or company.legal_name
    company.trade_name = (form.get('trade_name') or '').strip() or company.trade_name
    company.document = (form.get('document') or '').strip() or None
    company.email = (form.get('email') or '').strip() or None
    company.phone = (form.get('phone') or '').strip() or None
    company.whatsapp = (form.get('whatsapp') or '').strip() or None
    company.address = (form.get('address') or '').strip() or None
    company.city = (form.get('city') or '').strip() or None
    company.state = (form.get('state') or '').strip().upper() or None
    company.zip_code = (form.get('zip_code') or '').strip() or None
    if form.get('remove_logo') == 'on':
        company.logo_data = None
        company.logo_content_type = None
    upload = form.get('logo')
    if upload and getattr(upload, 'filename', ''):
        content_type = (getattr(upload, 'content_type', '') or '').lower()
        if content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
            flash(request, 'A logo deve ser PNG, JPG/JPEG ou WebP.', 'error')
            return RedirectResponse('/admin/empresa', 303)
        data = await upload.read()
        if len(data) > 2 * 1024 * 1024:
            flash(request, 'A logo deve ter no máximo 2 MB.', 'error')
            return RedirectResponse('/admin/empresa', 303)
        company.logo_data = data
        company.logo_content_type = content_type
    db.commit()
    flash(request, 'Dados da empresa atualizados.')
    return RedirectResponse('/admin/empresa', 303)


# ------------------------ LEMBRETES ------------------------
@app.get('/admin/lembretes')
def reminder_settings_get(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    settings = get_reminder_settings(db, operator.company_id)
    logs = db.scalars(select(ReminderLog).options(joinedload(ReminderLog.client)).where(ReminderLog.company_id == operator.company_id).order_by(ReminderLog.sent_at.desc()).limit(100)).all()
    return templates.TemplateResponse('reminder_settings.html', base_context(
        request, operator=operator, settings=settings, logs=logs, whatsapp_ready=whatsapp_api_ready()
    ))


@app.post('/admin/lembretes')
async def reminder_settings_post(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    form = await request.form()
    settings = get_reminder_settings(db, operator.company_id)
    settings.company_id = operator.company_id
    settings.enabled = form.get('enabled') == 'on'
    settings.send_time = (form.get('send_time') or '17:00').strip()
    try:
        settings.max_attempts = max(1, min(10, int(form.get('max_attempts') or 1)))
    except ValueError:
        settings.max_attempts = 1
    try:
        settings.interval_minutes = max(15, min(1440, int(form.get('interval_minutes') or 120)))
    except ValueError:
        settings.interval_minutes = 120
    settings.manual_message = (form.get('manual_message') or '').strip() or settings.manual_message
    db.commit()
    flash(request, 'Configuração de lembretes salva.')
    return RedirectResponse('/admin/lembretes', 303)


@app.post('/admin/lembretes/processar-agora')
def reminder_run_now(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    process_automatic_reminders_once()
    flash(request, 'Verificação de lembretes executada. Consulte o histórico abaixo.')
    return RedirectResponse('/admin/lembretes', 303)

# ------------------------ DASHBOARD ------------------------
@app.get('/admin')
def admin_dashboard(request: Request, target: str | None = None, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator:
        return RedirectResponse('/login', 303)
    target_date = parse_date(target, tomorrow_local())
    orders = db.scalars(select(Order).options(joinedload(Order.client), joinedload(Order.items).joinedload(OrderItem.product)).where(Order.company_id == operator.company_id, Order.delivery_date == target_date, Order.status == 'SUBMITTED').order_by(Order.created_at)).unique().all()
    active_clients = db.scalars(select(Client).where(Client.company_id == operator.company_id, Client.is_active == True).order_by(Client.company_name)).all()
    order_client_ids = {o.client_id for o in orders}
    missing = []
    for c in active_clients:
        if c.id not in order_client_ids:
            reason = client_block_reason(db, c)
            message = f'Olá, {c.trade_name or c.company_name}! Ainda não recebemos seu pedido para {target_date.strftime("%d/%m/%Y")}. Você pode fazer o pedido aqui: {PUBLIC_BASE_URL}/cliente/login'
            missing.append({'client': c, 'blocked_reason': reason, 'whatsapp_url': whatsapp_link(c.whatsapp or c.phone, message)})
    summary_rows = db.execute(
        select(Product.name, Product.unit, func.sum(OrderItem.quantity), func.sum(OrderItem.total))
        .join(OrderItem.product)
        .join(OrderItem.order)
        .where(Order.company_id == operator.company_id, Order.delivery_date == target_date, Order.status == 'SUBMITTED')
        .group_by(Product.id, Product.name, Product.unit)
        .order_by(func.sum(OrderItem.quantity).desc())
    ).all()
    total_sales = sum((Decimal(o.total or 0) for o in orders), Decimal('0'))
    avg_ticket = total_sales / len(orders) if orders else Decimal('0')
    overdue_count = db.scalar(select(func.count(Receivable.id)).where(Receivable.company_id == operator.company_id, Receivable.due_date < today_local(), Receivable.status != 'PAGO')) or 0
    db.commit()
    return templates.TemplateResponse('admin_dashboard.html', base_context(
        request, operator=operator, target_date=target_date, orders=orders, missing=missing,
        summary_rows=summary_rows, total_sales=total_sales, avg_ticket=avg_ticket,
        overdue_count=overdue_count,
        chart_labels=[r[0] for r in summary_rows], chart_values=[float(r[2] or 0) for r in summary_rows]
    ))

# ------------------------ PRODUTOS CRUD ------------------------
@app.get('/admin/produtos')
def products_list(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login', 303)
    products = db.scalars(select(Product).where(Product.company_id == operator.company_id).order_by(Product.is_active.desc(), Product.name)).all()
    return templates.TemplateResponse('products.html', base_context(request, operator=operator, products=products))


@app.get('/admin/produtos/novo')
def product_new_get(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login', 303)
    return templates.TemplateResponse('product_form.html', base_context(request, operator=operator, product=None))


@app.post('/admin/produtos/novo')
async def product_new_post(request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login', 303)
    form = await request.form()
    p = Product(company_id=operator.company_id, code=form.get('code','').strip(), name=form.get('name','').strip(), unit=form.get('unit','UN').strip().upper(), category=form.get('category','').strip() or None, default_price=parse_decimal(form.get('default_price')), is_active=form.get('is_active') == 'on')
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); flash(request, 'Já existe um produto com esse código.', 'error'); return RedirectResponse('/admin/produtos/novo',303)
    flash(request, 'Produto cadastrado com sucesso.')
    return RedirectResponse('/admin/produtos',303)


@app.get('/admin/produtos/{product_id}/editar')
def product_edit_get(product_id: int, request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login',303)
    product = db.get(Product, product_id)
    if not product or product.company_id != operator.company_id: raise HTTPException(404)
    return templates.TemplateResponse('product_form.html', base_context(request, operator=operator, product=product))


@app.post('/admin/produtos/{product_id}/editar')
async def product_edit_post(product_id: int, request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login',303)
    product = db.get(Product, product_id)
    if not product or product.company_id != operator.company_id: raise HTTPException(404)
    form = await request.form()
    product.code=form.get('code','').strip(); product.name=form.get('name','').strip(); product.unit=form.get('unit','UN').strip().upper(); product.category=form.get('category','').strip() or None; product.default_price=parse_decimal(form.get('default_price')); product.is_active=form.get('is_active')=='on'
    try: db.commit()
    except IntegrityError: db.rollback(); flash(request,'Código já utilizado por outro produto.','error'); return RedirectResponse(f'/admin/produtos/{product_id}/editar',303)
    flash(request,'Produto atualizado.')
    return RedirectResponse('/admin/produtos',303)


@app.post('/admin/produtos/{product_id}/excluir')
def product_delete(product_id: int, request: Request, db: Session = Depends(get_db)):
    operator = require_operator(request, db)
    if not operator: return RedirectResponse('/login',303)
    product = db.get(Product, product_id)
    if not product or product.company_id != operator.company_id: raise HTTPException(404)
    used = db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product_id)) or 0
    if used:
        product.is_active = False
        flash(request,'Produto possui histórico de pedidos e foi desativado para preservar os relatórios.')
    else:
        db.delete(product); flash(request,'Produto excluído.')
    db.commit()
    return RedirectResponse('/admin/produtos',303)

# ------------------------ DISPONIBILIDADE ------------------------
@app.get('/admin/disponibilidade')
def availability_get(request: Request, target: str | None = None, db: Session = Depends(get_db)):
    operator=require_operator(request,db)
    if not operator: return RedirectResponse('/login',303)
    target_date=parse_date(target,tomorrow_local())
    products=db.scalars(select(Product).where(Product.company_id==operator.company_id, Product.is_active==True).order_by(Product.category,Product.name)).all()
    rows=db.scalars(select(Availability).where(Availability.company_id==operator.company_id, Availability.sale_date==target_date)).all()
    amap={r.product_id:r for r in rows}
    return templates.TemplateResponse('availability.html',base_context(request,operator=operator,target_date=target_date,products=products,amap=amap))


@app.post('/admin/disponibilidade')
async def availability_post(request: Request, db: Session = Depends(get_db)):
    operator=require_operator(request,db)
    if not operator: return RedirectResponse('/login',303)
    form=await request.form(); target_date=parse_date(form.get('target_date'),tomorrow_local())
    products=db.scalars(select(Product).where(Product.company_id==operator.company_id, Product.is_active==True)).all()
    db.query(Availability).filter(Availability.company_id==operator.company_id, Availability.sale_date==target_date).delete(synchronize_session=False)
    for p in products:
        if form.get(f'available_{p.id}') == 'on':
            price_raw=form.get(f'price_{p.id}','').strip(); stock_raw=form.get(f'stock_{p.id}','').strip()
            db.add(Availability(company_id=operator.company_id, sale_date=target_date,product_id=p.id,price_override=parse_decimal(price_raw) if price_raw else None,stock_limit=parse_decimal(stock_raw) if stock_raw else None))
    db.commit(); flash(request,f'Disponibilidade de {target_date.strftime("%d/%m/%Y")} salva.')
    return RedirectResponse(f'/admin/disponibilidade?target={target_date.isoformat()}',303)

# ------------------------ CLIENTES CRUD ------------------------
@app.get('/admin/clientes')
def clients_list(request: Request, db: Session = Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    clients=db.scalars(select(Client).where(Client.company_id==operator.company_id).order_by(Client.is_active.desc(),Client.company_name)).all()
    rows=[]
    for c in clients:
        reason=client_block_reason(db,c); rows.append({'client':c,'block_reason':reason})
    db.commit()
    return templates.TemplateResponse('clients.html',base_context(request,operator=operator,rows=rows))


@app.get('/admin/clientes/novo')
def client_new_get(request: Request, db: Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    return templates.TemplateResponse('client_form.html',base_context(request,operator=operator,client=None))


@app.post('/admin/clientes/novo')
async def client_new_post(request: Request, db: Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    form=await request.form(); password=form.get('password','')
    if len(password)<8:
        flash(request,'A senha inicial deve ter no mínimo 8 caracteres.','error'); return RedirectResponse('/admin/clientes/novo',303)
    c=Client(company_id=operator.company_id, company_name=form.get('company_name','').strip(),trade_name=form.get('trade_name','').strip() or None,document=form.get('document','').strip() or None,contact_name=form.get('contact_name','').strip() or None,email=form.get('email','').strip().lower(),password_hash=hash_password(password),phone=form.get('phone','').strip() or None,whatsapp=form.get('whatsapp','').strip() or None,address=form.get('address','').strip() or None,city=form.get('city','').strip() or None,state=form.get('state','').strip().upper() or None,zip_code=form.get('zip_code','').strip() or None,payment_terms_days=int(form.get('payment_terms_days') or 7),credit_limit=parse_decimal(form.get('credit_limit')) if form.get('credit_limit','').strip() else None,manual_blocked=form.get('manual_blocked')=='on',blocked_reason=form.get('blocked_reason','').strip() or None,is_active=form.get('is_active')=='on',reminder_enabled=form.get('reminder_enabled')=='on')
    db.add(c)
    try:db.commit()
    except IntegrityError:db.rollback();flash(request,'Já existe um cliente com esse e-mail.','error');return RedirectResponse('/admin/clientes/novo',303)
    flash(request,'Cliente cadastrado com sucesso.')
    return RedirectResponse('/admin/clientes',303)


@app.get('/admin/clientes/{client_id}/editar')
def client_edit_get(client_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    client=db.get(Client,client_id)
    if not client or client.company_id != operator.company_id:raise HTTPException(404)
    return templates.TemplateResponse('client_form.html',base_context(request,operator=operator,client=client))


@app.post('/admin/clientes/{client_id}/editar')
async def client_edit_post(client_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    c=db.get(Client,client_id)
    if not c or c.company_id != operator.company_id:raise HTTPException(404)
    form=await request.form()
    c.company_name=form.get('company_name','').strip();c.trade_name=form.get('trade_name','').strip() or None;c.document=form.get('document','').strip() or None;c.contact_name=form.get('contact_name','').strip() or None;c.email=form.get('email','').strip().lower();c.phone=form.get('phone','').strip() or None;c.whatsapp=form.get('whatsapp','').strip() or None;c.address=form.get('address','').strip() or None;c.city=form.get('city','').strip() or None;c.state=form.get('state','').strip().upper() or None;c.zip_code=form.get('zip_code','').strip() or None;c.payment_terms_days=int(form.get('payment_terms_days') or 7);c.credit_limit=parse_decimal(form.get('credit_limit')) if form.get('credit_limit','').strip() else None;c.manual_blocked=form.get('manual_blocked')=='on';c.blocked_reason=form.get('blocked_reason','').strip() or None;c.is_active=form.get('is_active')=='on';c.reminder_enabled=form.get('reminder_enabled')=='on'
    if form.get('password','').strip():
        if len(form.get('password'))<8:flash(request,'Nova senha deve ter no mínimo 8 caracteres.','error');return RedirectResponse(f'/admin/clientes/{client_id}/editar',303)
        c.password_hash=hash_password(form.get('password'))
    try:db.commit()
    except IntegrityError:db.rollback();flash(request,'E-mail já utilizado por outro cliente.','error');return RedirectResponse(f'/admin/clientes/{client_id}/editar',303)
    flash(request,'Cliente atualizado.')
    return RedirectResponse('/admin/clientes',303)


@app.post('/admin/clientes/{client_id}/excluir')
def client_delete(client_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    c=db.get(Client,client_id)
    if not c or c.company_id != operator.company_id:raise HTTPException(404)
    used=db.scalar(select(func.count(Order.id)).where(Order.client_id==client_id)) or 0
    if used:
        c.is_active=False;flash(request,'Cliente possui histórico e foi desativado para preservar os relatórios.')
    else:
        db.query(PasswordResetToken).filter(PasswordResetToken.client_id==client_id).delete();db.delete(c);flash(request,'Cliente excluído.')
    db.commit();return RedirectResponse('/admin/clientes',303)

# ------------------------ USUÁRIOS / OPERADORES CRUD ------------------------
@app.get('/admin/usuarios')
def users_list(request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    users=db.scalars(select(User).where(User.company_id==operator.company_id).order_by(User.is_active.desc(),User.name)).all()
    return templates.TemplateResponse('users.html',base_context(request,operator=operator,users=users))


@app.get('/admin/usuarios/novo')
def user_new_get(request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    return templates.TemplateResponse('user_form.html',base_context(request,operator=operator,user=None))


@app.post('/admin/usuarios/novo')
async def user_new_post(request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    form=await request.form();password=form.get('password','')
    if len(password)<8:flash(request,'Senha deve ter no mínimo 8 caracteres.','error');return RedirectResponse('/admin/usuarios/novo',303)
    u=User(company_id=operator.company_id, name=form.get('name','').strip(),email=form.get('email','').strip().lower(),password_hash=hash_password(password),role=form.get('role','OPERADOR'),is_active=form.get('is_active')=='on');db.add(u)
    try:db.commit()
    except IntegrityError:db.rollback();flash(request,'E-mail já cadastrado.','error');return RedirectResponse('/admin/usuarios/novo',303)
    flash(request,'Operador cadastrado.')
    return RedirectResponse('/admin/usuarios',303)


@app.get('/admin/usuarios/{user_id}/editar')
def user_edit_get(user_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    user=db.get(User,user_id)
    if not user or user.company_id != operator.company_id:raise HTTPException(404)
    return templates.TemplateResponse('user_form.html',base_context(request,operator=operator,user=user))


@app.post('/admin/usuarios/{user_id}/editar')
async def user_edit_post(user_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    u=db.get(User,user_id)
    if not u or u.company_id != operator.company_id:raise HTTPException(404)
    form=await request.form();u.name=form.get('name','').strip();u.email=form.get('email','').strip().lower();u.role=form.get('role','OPERADOR');u.is_active=form.get('is_active')=='on'
    if form.get('password','').strip():
        if len(form.get('password'))<8:flash(request,'Senha deve ter no mínimo 8 caracteres.','error');return RedirectResponse(f'/admin/usuarios/{user_id}/editar',303)
        u.password_hash=hash_password(form.get('password'))
    try:db.commit()
    except IntegrityError:db.rollback();flash(request,'E-mail já utilizado.','error');return RedirectResponse(f'/admin/usuarios/{user_id}/editar',303)
    flash(request,'Operador atualizado.');return RedirectResponse('/admin/usuarios',303)


@app.post('/admin/usuarios/{user_id}/excluir')
def user_delete(user_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    if operator.id==user_id:flash(request,'Você não pode excluir seu próprio usuário.','error');return RedirectResponse('/admin/usuarios',303)
    u=db.get(User,user_id)
    if u and u.company_id==operator.company_id:
        used=db.scalar(select(func.count(Receipt.id)).where(Receipt.operator_id==u.id)) or 0
        if used:
            u.is_active=False;db.commit();flash(request,'Operador possui histórico financeiro e foi desativado para preservar os recibos.')
        else:
            db.delete(u);db.commit();flash(request,'Operador excluído.')
    return RedirectResponse('/admin/usuarios',303)

# ------------------------ PEDIDO CLIENTE ------------------------
@app.get('/cliente/pedido')
def client_order_get(request:Request,db:Session=Depends(get_db)):
    client=require_client(request,db)
    if not client:return RedirectResponse('/cliente/login',303)
    target=tomorrow_local();block_reason=client_block_reason(db,client);db.commit()
    avail=db.scalars(select(Availability).options(joinedload(Availability.product)).where(Availability.company_id==client.company_id, Availability.sale_date==target).order_by(Availability.product_id)).all()
    avail=sorted(avail,key=lambda a:(a.product.category or '',a.product.name))
    order=db.scalar(select(Order).options(joinedload(Order.items)).where(Order.company_id==client.company_id, Order.client_id==client.id,Order.delivery_date==target,Order.status=='SUBMITTED'))
    quantities={i.product_id:i.quantity for i in order.items} if order else {}
    return templates.TemplateResponse('client_order.html',base_context(request,client_session=client,client=client,target_date=target,avail=avail,quantities=quantities,order=order,block_reason=block_reason,order_open=order_open_for(target),cutoff_hour=ORDER_CUTOFF_HOUR))


@app.post('/cliente/pedido')
async def client_order_post(request:Request,db:Session=Depends(get_db)):
    client=require_client(request,db)
    if not client:return RedirectResponse('/cliente/login',303)
    target=tomorrow_local();block_reason=client_block_reason(db,client)
    if block_reason:db.commit();flash(request,block_reason,'error');return RedirectResponse('/cliente/pedido',303)
    if not order_open_for(target):flash(request,'O prazo para o pedido do próximo dia está encerrado.','error');return RedirectResponse('/cliente/pedido',303)
    form=await request.form();avail=db.scalars(select(Availability).options(joinedload(Availability.product)).where(Availability.company_id==client.company_id, Availability.sale_date==target)).all()
    requested=[]; errors=[]
    existing=db.scalar(select(Order).options(joinedload(Order.items)).where(Order.company_id==client.company_id, Order.client_id==client.id,Order.delivery_date==target,Order.status=='SUBMITTED'))
    existing_id=existing.id if existing else -1
    for a in avail:
        q=parse_decimal(form.get(f'qty_{a.product_id}'))
        if q < 0:
            errors.append(f'{a.product.name}: a quantidade não pode ser negativa.')
            continue
        if q != q.to_integral_value():
            errors.append(f'{a.product.name}: informe somente unidades inteiras (1, 2, 3...).')
            continue
        q = q.to_integral_value()
        if q>0:
            if a.stock_limit is not None:
                other_qty=db.scalar(select(func.coalesce(func.sum(OrderItem.quantity),0)).join(Order).where(Order.company_id==client.company_id, Order.delivery_date==target,OrderItem.product_id==a.product_id,Order.id!=existing_id,Order.status=='SUBMITTED')) or Decimal('0')
                if Decimal(other_qty)+q>Decimal(a.stock_limit):
                    remaining=max(Decimal(a.stock_limit)-Decimal(other_qty),Decimal('0'))
                    errors.append(f'{a.product.name}: disponível restante {qty(remaining)} {a.product.unit}.')
                    continue
            price=Decimal(a.price_override if a.price_override is not None else a.product.default_price)
            requested.append((a.product_id,q,price,(q*price).quantize(Decimal('0.01'))))
    if errors:
        flash(request,' '.join(errors),'error');return RedirectResponse('/cliente/pedido',303)
    if not requested:
        flash(request,'Informe a quantidade de pelo menos um produto.','error');return RedirectResponse('/cliente/pedido',303)
    order=existing
    if not order:
        order=Order(company_id=client.company_id, number='TEMP',client_id=client.id,delivery_date=target,status='SUBMITTED',notes=form.get('notes','').strip() or None,total=0);db.add(order);db.flush();order.number=f'PED-{target.strftime("%Y%m%d")}-{order.id:05d}'
    else:
        order.notes=form.get('notes','').strip() or None;order.items.clear();db.flush()
    total=Decimal('0')
    for product_id,q,price,line_total in requested:
        order.items.append(OrderItem(product_id=product_id,quantity=q,unit_price=price,total=line_total));total+=line_total
    order.total=total;order.updated_at=datetime.utcnow();db.flush()
    due_date=target+timedelta(days=client.payment_terms_days or 0)
    rec=db.scalar(select(Receivable).where(Receivable.company_id==client.company_id, Receivable.order_id==order.id))
    if not rec:
        rec=Receivable(company_id=client.company_id, order_id=order.id,client_id=client.id,due_date=due_date,amount=total,amount_paid=0,status='PENDENTE');db.add(rec)
    else:
        rec.amount=total;rec.due_date=due_date;update_receivable_status(rec)
    db.commit()
    return RedirectResponse(f'/cliente/pedidos/{order.id}?salvo=1',303)


def client_order_can_change(order: Order):
    return order.status == 'SUBMITTED' and order_open_for(order.delivery_date)


@app.get('/cliente/historico')
def client_history(request:Request,db:Session=Depends(get_db)):
    client=require_client(request,db)
    if not client:return RedirectResponse('/cliente/login',303)
    orders=db.scalars(select(Order).options(joinedload(Order.items).joinedload(OrderItem.product), joinedload(Order.receivable)).where(Order.company_id==client.company_id, Order.client_id==client.id).order_by(Order.delivery_date.desc()).limit(50)).unique().all()
    return templates.TemplateResponse('client_history.html',base_context(request,client_session=client,client=client,orders=orders,client_order_can_change=client_order_can_change))


@app.get('/cliente/pedidos/{order_id}')
def client_order_detail(order_id:int,request:Request,db:Session=Depends(get_db)):
    client=require_client(request,db)
    if not client:return RedirectResponse('/cliente/login',303)
    order=db.scalar(select(Order).options(joinedload(Order.items).joinedload(OrderItem.product), joinedload(Order.receivable)).where(
        Order.id==order_id, Order.company_id==client.company_id, Order.client_id==client.id
    ))
    if not order:raise HTTPException(404)
    can_change=client_order_can_change(order)
    has_payment=bool(order.receivable and Decimal(order.receivable.amount_paid or 0)>0)
    saved=request.query_params.get('salvo')=='1'
    return templates.TemplateResponse('client_order_detail.html',base_context(
        request,client_session=client,client=client,order=order,can_change=can_change,has_payment=has_payment,saved=saved
    ))


@app.post('/cliente/pedidos/{order_id}/excluir')
def client_order_delete(order_id:int,request:Request,db:Session=Depends(get_db)):
    client=require_client(request,db)
    if not client:return RedirectResponse('/cliente/login',303)
    order=db.scalar(select(Order).options(joinedload(Order.receivable)).where(
        Order.id==order_id, Order.company_id==client.company_id, Order.client_id==client.id
    ))
    if not order:raise HTTPException(404)
    if not client_order_can_change(order):
        flash(request,'Este pedido não pode mais ser excluído porque o prazo de alteração encerrou.','error')
        return RedirectResponse(f'/cliente/pedidos/{order.id}',303)
    if order.receivable and Decimal(order.receivable.amount_paid or 0)>0:
        flash(request,'Este pedido já possui pagamento registrado e não pode ser excluído. Entre em contato com a horta.','error')
        return RedirectResponse(f'/cliente/pedidos/{order.id}',303)
    number=order.number
    db.delete(order);db.commit()
    flash(request,f'Pedido {number} excluído. Se desejar, você pode fazer um novo pedido enquanto o prazo estiver aberto.','success')
    return RedirectResponse('/cliente/pedido',303)

# ------------------------ PEDIDOS ADMIN / ROMANEIO ------------------------
@app.get('/admin/pedidos/{order_id}')
def order_detail(order_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    order=db.scalar(select(Order).options(joinedload(Order.client),joinedload(Order.items).joinedload(OrderItem.product)).where(Order.id==order_id, Order.company_id==operator.company_id))
    if not order:raise HTTPException(404)
    return templates.TemplateResponse('order_detail.html',base_context(request,operator=operator,order=order))


@app.get('/admin/pedidos/{order_id}/romaneio')
def order_romaneio(order_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    order=db.scalar(select(Order).options(joinedload(Order.client),joinedload(Order.items).joinedload(OrderItem.product)).where(Order.id==order_id, Order.company_id==operator.company_id))
    if not order:raise HTTPException(404)
    return templates.TemplateResponse('romaneio.html',base_context(request,operator=operator,orders=[order],print_title=f'Romaneio {order.number}'))


@app.get('/admin/romaneios')
def all_romaneios(request:Request,target:str|None=None,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    target_date=parse_date(target,tomorrow_local())
    orders=db.scalars(select(Order).options(joinedload(Order.client),joinedload(Order.items).joinedload(OrderItem.product)).where(Order.company_id==operator.company_id, Order.delivery_date==target_date,Order.status=='SUBMITTED').order_by(Order.client_id)).unique().all()
    return templates.TemplateResponse('romaneio.html',base_context(request,operator=operator,orders=orders,print_title=f'Romaneios {target_date.strftime("%d/%m/%Y")}'))

# ------------------------ CONTAS A RECEBER ------------------------
@app.get('/admin/receber')
def receivables_list(request:Request,status:str|None=None,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    recs=db.scalars(select(Receivable).options(joinedload(Receivable.client),joinedload(Receivable.order)).where(Receivable.company_id==operator.company_id).order_by(Receivable.due_date.asc(), Receivable.id.asc())).all()
    for r in recs:update_receivable_status(r)
    db.commit()
    display_recs=[r for r in recs if not status or r.status==status]
    total_open=sum((receivable_outstanding(r) for r in recs if r.status!='PAGO'),Decimal('0'))
    open_by_client={}
    for r in recs:
        out=receivable_outstanding(r)
        if out<=0: continue
        row=open_by_client.setdefault(r.client_id, {'client':r.client,'titles':[],'total':Decimal('0'),'oldest':r.due_date})
        row['titles'].append(r);row['total']+=out;row['oldest']=min(row['oldest'],r.due_date)
    groups=sorted(open_by_client.values(), key=lambda x: ((x['client'].trade_name or x['client'].company_name).lower(), x['oldest']))
    return templates.TemplateResponse('receivables.html',base_context(request,operator=operator,recs=display_recs,total_open=total_open,status=status,receivable_outstanding=receivable_outstanding,groups=groups))


@app.get('/admin/receber/cliente/{client_id}')
def receivables_client(client_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    client=db.scalar(select(Client).where(Client.id==client_id,Client.company_id==operator.company_id))
    if not client or client.company_id != operator.company_id:raise HTTPException(404)
    recs=db.scalars(select(Receivable).options(joinedload(Receivable.order)).where(Receivable.client_id==client_id,Receivable.company_id==operator.company_id).order_by(Receivable.due_date.asc(),Receivable.id.asc())).all()
    for r in recs:update_receivable_status(r)
    db.commit()
    open_recs=[r for r in recs if receivable_outstanding(r)>0]
    total=sum((receivable_outstanding(r) for r in open_recs),Decimal('0'))
    return templates.TemplateResponse('receivables_client.html',base_context(request,operator=operator,client=client,recs=open_recs,total=total,receivable_outstanding=receivable_outstanding))


@app.post('/admin/receber/{receivable_id}/pagamento')
def receivable_payment(receivable_id:int,request:Request,payment_amount:str=Form(...),payment_method:str=Form(''),notes:str=Form(''),db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    r=db.scalar(select(Receivable).options(joinedload(Receivable.order),joinedload(Receivable.client)).where(Receivable.id==receivable_id,Receivable.company_id==operator.company_id))
    if not r:raise HTTPException(404)
    amount=parse_decimal(payment_amount)
    if amount<=0:flash(request,'Informe um valor de pagamento válido.','error');return RedirectResponse('/admin/receber',303)
    receipt=create_receipt(db,r.client,operator,[(r,amount)],payment_method,notes)
    if not receipt:
        flash(request,'Não havia saldo para receber.','error');return RedirectResponse('/admin/receber',303)
    return RedirectResponse(f'/admin/recibos/{receipt.id}',303)


@app.post('/admin/receber/cliente/{client_id}/baixar-todos')
def receivables_pay_all(client_id:int,request:Request,payment_method:str=Form(''),notes:str=Form(''),db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    client=db.scalar(select(Client).where(Client.id==client_id,Client.company_id==operator.company_id))
    if not client or client.company_id != operator.company_id:raise HTTPException(404)
    recs=db.scalars(select(Receivable).options(joinedload(Receivable.order)).where(Receivable.client_id==client_id,Receivable.company_id==operator.company_id).order_by(Receivable.due_date.asc())).all()
    allocations=[(r,receivable_outstanding(r)) for r in recs if receivable_outstanding(r)>0]
    receipt=create_receipt(db,client,operator,allocations,payment_method,notes)
    if not receipt:
        flash(request,'O cliente não possui contas em aberto.','error');return RedirectResponse(f'/admin/receber/cliente/{client_id}',303)
    return RedirectResponse(f'/admin/recibos/{receipt.id}',303)


@app.get('/admin/recibos')
def receipts_list(request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    rows=db.scalars(select(Receipt).options(joinedload(Receipt.client)).where(Receipt.company_id==operator.company_id).order_by(Receipt.payment_date.desc(),Receipt.id.desc()).limit(500)).all()
    return templates.TemplateResponse('receipts.html',base_context(request,operator=operator,receipts=rows))


@app.get('/admin/recibos/{receipt_id}')
def receipt_print(receipt_id:int,request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    receipt=db.scalar(select(Receipt).options(joinedload(Receipt.client),joinedload(Receipt.operator),joinedload(Receipt.items)).where(Receipt.id==receipt_id,Receipt.company_id==operator.company_id))
    if not receipt:raise HTTPException(404)
    return templates.TemplateResponse('receipt.html',base_context(request,operator=operator,receipt=receipt,company=receipt.company))

# ------------------------ RELATÓRIOS ------------------------
def period_bounds(start:str|None,end:str|None):
    e=parse_date(end,today_local());s=parse_date(start,e-timedelta(days=30));return s,e


@app.get('/admin/relatorios/vendas')
def report_sales(request:Request,start:str|None=None,end:str|None=None,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    s,e=period_bounds(start,end)
    by_product=db.execute(select(Product.name,Product.unit,func.sum(OrderItem.quantity),func.sum(OrderItem.total)).join(OrderItem.product).join(OrderItem.order).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED').group_by(Product.id,Product.name,Product.unit).order_by(func.sum(OrderItem.total).desc())).all()
    by_client=db.execute(select(Client.company_name,func.count(Order.id),func.sum(Order.total)).join(Order.client).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED').group_by(Client.id,Client.company_name).order_by(func.sum(Order.total).desc())).all()
    detail=db.execute(select(Client.company_name,Product.name,Product.unit,func.sum(OrderItem.quantity),func.sum(OrderItem.total)).select_from(OrderItem).join(Order,OrderItem.order_id==Order.id).join(Client,Order.client_id==Client.id).join(Product,OrderItem.product_id==Product.id).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED').group_by(Client.id,Client.company_name,Product.id,Product.name,Product.unit).order_by(Client.company_name,Product.name)).all()
    total=db.scalar(select(func.coalesce(func.sum(Order.total),0)).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED')) or 0
    return templates.TemplateResponse('report_sales.html',base_context(request,operator=operator,start=s,end=e,by_product=by_product,by_client=by_client,detail=detail,total=total))


@app.get('/admin/relatorios/inadimplentes')
def report_overdue(request:Request,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    recs=db.scalars(select(Receivable).options(joinedload(Receivable.client),joinedload(Receivable.order)).where(Receivable.company_id==operator.company_id, Receivable.status!='PAGO').order_by(Receivable.due_date)).all()
    overdue=[]
    for r in recs:
        update_receivable_status(r)
        if receivable_outstanding(r)>0 and r.due_date<today_local():overdue.append(r)
    db.commit();total=sum((receivable_outstanding(r) for r in overdue),Decimal('0'))
    return templates.TemplateResponse('report_overdue.html',base_context(request,operator=operator,recs=overdue,total=total,receivable_outstanding=receivable_outstanding))


@app.get('/admin/relatorios/mais-vendidos')
def report_bestsellers(request:Request,start:str|None=None,end:str|None=None,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    s,e=period_bounds(start,end)
    rows=db.execute(select(Product.name,Product.unit,func.sum(OrderItem.quantity),func.sum(OrderItem.total)).join(OrderItem.product).join(OrderItem.order).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED').group_by(Product.id,Product.name,Product.unit).order_by(func.sum(OrderItem.quantity).desc())).all()
    return templates.TemplateResponse('report_bestsellers.html',base_context(request,operator=operator,start=s,end=e,rows=rows,chart_labels=[r[0] for r in rows[:10]],chart_values=[float(r[2] or 0) for r in rows[:10]]))


@app.get('/admin/relatorios/diagnostico')
def report_diagnostics(request:Request,start:str|None=None,end:str|None=None,db:Session=Depends(get_db)):
    operator=require_operator(request,db)
    if not operator:return RedirectResponse('/login',303)
    s,e=period_bounds(start,end)
    orders=db.scalars(select(Order).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED')).all()
    total=sum((Decimal(o.total or 0) for o in orders),Decimal('0'));avg=total/len(orders) if orders else Decimal('0')
    daily=db.execute(select(Order.delivery_date,func.count(Order.id),func.sum(Order.total)).where(Order.company_id==operator.company_id, Order.delivery_date.between(s,e),Order.status=='SUBMITTED').group_by(Order.delivery_date).order_by(Order.delivery_date)).all()
    active_clients=db.scalars(select(Client).where(Client.company_id==operator.company_id, Client.is_active==True)).all();buyers=set(o.client_id for o in orders);inactive_period=[c for c in active_clients if c.id not in buyers]
    open_rec=db.scalars(select(Receivable).where(Receivable.company_id==operator.company_id, Receivable.status!='PAGO')).all();open_total=sum((receivable_outstanding(r) for r in open_rec),Decimal('0'))
    return templates.TemplateResponse('report_diagnostics.html',base_context(request,operator=operator,start=s,end=e,total=total,avg=avg,order_count=len(orders),daily=daily,inactive_period=inactive_period,open_total=open_total))
