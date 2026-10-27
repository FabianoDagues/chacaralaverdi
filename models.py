from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(180), default='Minha Horta')
    trade_name: Mapped[str] = mapped_column(String(180), default='Minha Horta')
    document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(220), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(15), nullable=True)
    self_registration_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    self_registration_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    self_registration_requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    self_registration_payment_terms_days: Mapped[int] = mapped_column(Integer, default=7)
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default='OPERADOR')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company = relationship('Company')


class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (UniqueConstraint('company_id', 'code', name='uq_product_company_code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    unit: Mapped[str] = mapped_column(String(30), default='UN')
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_price: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company = relationship('Company')


class Client(Base):
    __tablename__ = 'clients'
    __table_args__ = (UniqueConstraint('company_id', 'email', name='uq_client_company_email'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    company_name: Mapped[str] = mapped_column(String(180))
    trade_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(180), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(220), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(15), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=7)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(12,2), nullable=True)
    manual_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company = relationship('Company')
    orders = relationship('Order', back_populates='client')


class Availability(Base):
    __tablename__ = 'availability'
    __table_args__ = (UniqueConstraint('company_id','sale_date','product_id', name='uq_availability_company_date_product'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'))
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(12,2), nullable=True)
    stock_limit: Mapped[Decimal | None] = mapped_column(Numeric(12,3), nullable=True)
    product = relationship('Product')
    company = relationship('Company')


class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id'))
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default='SUBMITTED')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    company = relationship('Company')
    client = relationship('Client', back_populates='orders')
    items = relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')
    receivable = relationship('Receivable', back_populates='order', uselist=False, cascade='all, delete-orphan')


class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12,3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12,2))
    total: Mapped[Decimal] = mapped_column(Numeric(12,2))
    order = relationship('Order', back_populates='items')
    product = relationship('Product')


class Receivable(Base):
    __tablename__ = 'receivables'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id'))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    status: Mapped[str] = mapped_column(String(20), default='PENDENTE')
    notes: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    company = relationship('Company')
    order = relationship('Order', back_populates='receivable')
    client = relationship('Client')


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_tokens'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id', ondelete='CASCADE'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client = relationship('Client')
    company = relationship('Company')


class Receipt(Base):
    __tablename__ = 'receipts'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id'))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)
    payment_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company = relationship('Company')
    client = relationship('Client')
    operator = relationship('User')
    items = relationship('ReceiptItem', back_populates='receipt', cascade='all, delete-orphan')


class ReceiptItem(Base):
    __tablename__ = 'receipt_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey('receipts.id', ondelete='CASCADE'))
    receivable_id: Mapped[int | None] = mapped_column(ForeignKey('receivables.id', ondelete='SET NULL'), nullable=True)
    order_number: Mapped[str] = mapped_column(String(40))
    order_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2))
    receipt = relationship('Receipt', back_populates='items')
    receivable = relationship('Receivable')


class ReminderSettings(Base):
    __tablename__ = 'reminder_settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), unique=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    send_time: Mapped[str] = mapped_column(String(5), default='17:00')
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=120)
    manual_message: Mapped[str] = mapped_column(Text, default='Olá, {nome}! Ainda não recebemos seu pedido para {data}. Faça seu pedido aqui: {link}')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    company = relationship('Company')


class ReminderLog(Base):
    __tablename__ = 'reminder_logs'
    __table_args__ = (UniqueConstraint('company_id','client_id','target_date','attempt_no', name='uq_reminder_company_client_date_attempt'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), default=1)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id', ondelete='CASCADE'))
    target_date: Mapped[date] = mapped_column(Date, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='PROCESSANDO')
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company = relationship('Company')
    client = relationship('Client')
