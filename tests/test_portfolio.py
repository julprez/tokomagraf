"""Tests para tokomagraf — solo precio BTC desde CoinGecko."""

import pytest
from decimal import Decimal

from portfolio import fetch_btc_price, fetch_btc_price_detail, format_usd


@pytest.mark.asyncio
async def test_fetch_btc_price():
    """Verifica que se puede obtener el precio de BTC desde CoinGecko."""
    price = await fetch_btc_price()
    assert price is not None
    assert price.price_usd > 0
    assert price.updated_at is not None


@pytest.mark.asyncio
async def test_fetch_btc_price_detail():
    """Verifica que se puede obtener el detalle del precio de BTC."""
    detail = await fetch_btc_price_detail()
    assert detail is not None
    assert detail.price_usd > 0
    assert detail.updated_at is not None


def test_format_usd():
    """Verifica el formateo de USD."""
    assert format_usd(Decimal("1234.56")) == "$1,234.56"
    assert format_usd(Decimal("-500")) == "-$500.00"
    assert format_usd(Decimal("0")) == "$0.00"


def test_format_usd_rounding():
    """Verifica que se redondea a 2 decimales."""
    assert format_usd(Decimal("1234.567")) == "$1,234.57"
    assert format_usd(Decimal("1234.564")) == "$1,234.56"
