# =============================================================
# schemas.py — Esquemas Pydantic
# =============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class SeedPhraseGenerate(BaseModel):
    pass


class SeedPhraseLogin(BaseModel):
    words: list[str] = Field(..., min_length=6, max_length=6)
    name: Optional[str] = None


class SeedPhraseResponse(BaseModel):
    words: list[str]
    access_token: str
    token_type: str = "bearer"
    is_new: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Operations ──

class OperationCreate(BaseModel):
    tipo: str = Field(..., pattern="^(buy|sell|deposit|withdraw)$")
    activo: str = Field(..., pattern="^(BTC|USDC|EUR)$")
    cantidad: float = Field(..., gt=0)
    precio: float = Field(..., gt=0)
    comision: float = Field(default=0.0, ge=0)
    fecha: Optional[datetime] = None
    notes: Optional[str] = ""


class OperationOut(BaseModel):
    id: int
    tipo: str
    activo: str
    cantidad: float
    precio: float
    comision: float
    fecha: datetime
    notes: str

    model_config = {"from_attributes": True}


# ── Portfolio ──

class PortfolioOut(BaseModel):
    btc_actual: float
    usdc_actual: float
    eur_actual: float
    capital_aportado: float
    beneficio_total: float
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard ──

class DashboardData(BaseModel):
    # Balances
    btc_balance: float
    usdc_balance: float

    # Precios
    btc_price: float
    btc_change_24h: Optional[float] = None

    # Valor y rentabilidad
    portfolio_value: float
    total_invested: float
    total_pnl: float
    total_pnl_pct: float

    # Precio medio
    avg_btc_price: Optional[float] = None

    # Beneficios
    daily_profit: Optional[float] = None
    monthly_profit: Optional[float] = None
    annualized_return: Optional[float] = None

    # Metadata
    trade_count: int
    first_trade_date: Optional[str] = None
    updated_at: str


# ── Exchanges ──

class ExchangeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)


class ExchangeOut(BaseModel):
    id: int
    name: str
    api_key: str  # masked in response
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Alerts ──

class AlertCreate(BaseModel):
    alert_type: str = Field(..., pattern="^(price_above|price_below|profit_target|loss_limit)$")
    target_value: float = Field(..., gt=0)
    asset: str = Field(default="BTC", pattern="^(BTC|USDC|USDT)$")
    note: Optional[str] = ""


class AlertOut(BaseModel):
    id: int
    alert_type: str
    target_value: float
    asset: str
    note: str
    active: bool
    triggered: bool
    created_at: datetime
    triggered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── User Profile ──

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=6)


# ── Notifications ──

class NotificationOut(BaseModel):
    id: int
    alert_id: Optional[int] = None
    title: str
    message: str
    notif_type: str
    target_value: Optional[float] = None
    current_price: Optional[float] = None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── DCA ──

class DcaConfigUpdate(BaseModel):
    frequency: Optional[str] = Field(None, pattern="^(weekly|monthly)$")
    day: Optional[int] = Field(None, ge=0, le=28)
    active: Optional[bool] = None


# ── Daily History ──

class DailyHistoryOut(BaseModel):
    fecha: date
    valor_portfolio: float
    ganancia_dia: float
    btc: float
    usdc: float

    model_config = {"from_attributes": True}
