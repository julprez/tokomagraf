# =============================================================
# models.py — Modelos SQLAlchemy
# =============================================================

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    ForeignKey, Enum as SAEnum, Boolean, Date, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


def _utcnow():
    """Retorna datetime naive en UTC para almacenar en TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="Usuario")
    email = Column(String(255), unique=True, nullable=True, index=True)
    password = Column(String(255), nullable=True)
    seed_phrase_hash = Column(String(255), nullable=True, unique=True)
    created_at = Column(DateTime, default=_utcnow)

    exchanges = relationship("Exchange", back_populates="user", cascade="all, delete-orphan")
    operations = relationship("Operation", back_populates="user", cascade="all, delete-orphan")


class Exchange(Base):
    __tablename__ = "exchanges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(50), nullable=False)
    api_key = Column(Text, nullable=False)
    api_secret = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="exchanges")


class Operation(Base):
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tipo = Column(String(10), nullable=False)  # buy, sell, deposit, withdraw
    activo = Column(String(10), nullable=False)  # BTC, USDC, EUR
    cantidad = Column(Float, nullable=False)
    precio = Column(Float, nullable=False)
    comision = Column(Float, default=0.0)
    fecha = Column(DateTime, default=_utcnow)
    notes = Column(Text, default="")

    user = relationship("User", back_populates="operations")


class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    btc_actual = Column(Float, default=0.0)
    usdc_actual = Column(Float, default=0.0)
    eur_actual = Column(Float, default=0.0)
    capital_aportado = Column(Float, default=0.0)
    beneficio_total = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class DailyHistory(Base):
    __tablename__ = "daily_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    valor_portfolio = Column(Float, nullable=False)
    ganancia_dia = Column(Float, default=0.0)
    btc = Column(Float, default=0.0)
    usdc = Column(Float, default=0.0)

    user = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notif_type = Column(String(20), nullable=False)
    target_value = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User")
    alert = relationship("Alert")


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    total_return_pct = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    avg_daily_return_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    portfolio_value = Column(Float, default=0.0)
    raw_data = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "fecha", name="uq_user_daily_summary"),
    )


class DcaStrategy(Base):
    __tablename__ = "dca_strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    frequency = Column(String(10), nullable=False, default="weekly")  # weekly | monthly
    day = Column(Integer, nullable=False, default=1)  # 0=Lun..6=Dom para weekly, 1-28 para monthly
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alert_type = Column(String(20), nullable=False)  # price_above, price_below, profit_target, loss_limit
    target_value = Column(Float, nullable=False)
    asset = Column(String(10), default="BTC")
    note = Column(Text, default="")
    active = Column(Boolean, default=True)
    triggered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    triggered_at = Column(DateTime, nullable=True)

    user = relationship("User")
