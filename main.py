# =============================================================
# main.py — tokomagraf Gestor de Cartera Cripto
# Panel diario + trades + recomendaciones
# =============================================================

import logging
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import card_renderer
import portfolio

# ── Configuración ────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tokomagraf_bot")


# ═════════════════════════════════════════════════════════════
#  Background Alert Checker
# ═════════════════════════════════════════════════════════════


async def check_alerts_background(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job de background que verifica alertas de precio cada 5 minutos.
    Envía notificaciones a todos los chats registrados."""
    try:
        price_data = await portfolio.fetch_btc_price()
        if not price_data:
            return

        triggered = portfolio.check_alerts(price_data.price_usd)
        if not triggered:
            return

        chat_ids = portfolio.get_all_chat_ids()
        if not chat_ids:
            logger.info("🚨 %d alertas disparadas, pero no hay chats registrados.", len(triggered))
            return

        for alert in triggered:
            msg = portfolio.format_alert_triggered(alert, price_data.price_usd)
            logger.info("🚨 Alerta #%d disparada: %s", alert.id, alert.type)
            for chat_id in chat_ids:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning("Error enviando alerta a chat %s: %s", chat_id, e)
    except Exception as e:
        logger.warning("Error en check_alerts_background: %s", e)


# ═════════════════════════════════════════════════════════════
#  Menú de navegación
# ═════════════════════════════════════════════════════════════


def _back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="nav_main")],
    ])


def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Panel de Cartera", callback_data="nav_dashboard")],
        [InlineKeyboardButton("💰 Precio BTC", callback_data="nav_precio"),
         InlineKeyboardButton("📊 Gráfica BTC", callback_data="nav_grafica")],
        [InlineKeyboardButton("📈 Análisis Técnico", callback_data="nav_analisis"),
         InlineKeyboardButton("🔄 Swap", callback_data="nav_swap")],
        [InlineKeyboardButton("💹 Evolución Patrimonio", callback_data="nav_patrimonio"),
         InlineKeyboardButton("🔔 Alertas", callback_data="nav_alertas")],
        [InlineKeyboardButton("📋 Ayuda", callback_data="nav_ayuda")],
    ])


# ═════════════════════════════════════════════════════════════
#  Handlers — Comandos
# ═════════════════════════════════════════════════════════════


def _dashboard_text(data: portfolio.PortfolioData) -> str:
    """Versión texto del dashboard (fallback si falla la imagen)."""
    lines = [
        "📊 **Panel de Cartera**",
        "",
        f"💰 **Patrimonio Total:** {portfolio.format_usd(data.portfolio_value)}",
        f"📈 P&L: {portfolio.format_pct(data.total_pnl_pct)} ({portfolio.format_usd(data.total_pnl)})",
        "",
        f"₿ **BTC:** {portfolio.format_btc(data.btc_balance)}",
        f"   Precio medio: {portfolio.format_usd(data.avg_btc_price) if data.avg_btc_price else '—'}",
        f"   Precio actual: {portfolio.format_usd(data.btc_price)}",
        f"   Objetivo ({data.target_pct:.0f}%): {portfolio.format_usd(data.target_price) if data.target_price else '—'}",
        "",
        f"🔵 **USDC:** {portfolio.format_usd(data.usdc_balance)}",
        f"💰 **Capital aportado:** {portfolio.format_usd(data.total_invested)}",
        "",
        f"📋 **Trades:** {data.trade_count}",
        "",
    ]

    if data.daily_profit is not None:
        lines.append(f"📈 **Hoy:** {portfolio.format_usd(data.daily_profit)}")
    if data.monthly_profit is not None:
        lines.append(f"📆 **Este mes:** {portfolio.format_usd(data.monthly_profit)}")
    if data.annualized_return is not None:
        lines.append(f"📊 **Anualizado:** {portfolio.format_pct(data.annualized_return)}")
    if data.progress_to_target is not None:
        lines.append(f"🎯 **Progreso:** {data.progress_to_target:.1f}% hacia el objetivo")

    lines.extend([
        "",
        f"**{data.recommendation}**",
        f"_{data.recommendation_explanation}_",
        "",
        f"🕐 {data.updated_at}",
    ])

    return "\n".join(lines)


async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start — panel de cartera + bienvenida."""
    user = update.effective_user

    # Registrar chat_id para notificaciones de alertas
    if user:
        portfolio.register_chat_id(update.effective_chat.id, user.first_name or "")

    msg = await update.message.reply_text(
        f"👋 **¡Bienvenido, {user.first_name}!** 🟠\n\n"
        f"Generando panel de cartera…",
        parse_mode="Markdown",
    )

    data = await portfolio.get_dashboard_data()
    if not data:
        await msg.edit_text(
            f"👋 **¡Bienvenido, {user.first_name}!**\n\n"
            f"No se pudo obtener el panel de cartera. "
            f"Si es tu primera vez, registrá tus trades con /comprar.\n\n"
            f"Usá /menu para explorar.",
            parse_mode="Markdown",
            reply_markup=_main_menu(),
        )
        return

    try:
        image_bytes = await card_renderer.generate_dashboard_card(data)
    except Exception as e:
        logger.error("Error generando dashboard: %s", e)
        image_bytes = None

    if image_bytes:
        photo = BytesIO(image_bytes)
        photo.name = "dashboard.png"
        caption = (
            f"👋 **¡Bienvenido, {user.first_name}!** 🟠\n"
            f"📊 **Panel de Cartera**"
        )
        await msg.delete()
        await update.message.reply_photo(
            photo=photo, caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_dashboard"),
                 InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
            ]),
        )
    else:
        text = (
            f"👋 **¡Bienvenido, {user.first_name}!**\n\n"
            + _dashboard_text(data)
        )
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=_main_menu())


async def bot_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /dashboard — muestra el panel de cartera."""
    user = update.effective_user
    if user:
        portfolio.register_chat_id(update.effective_chat.id, user.first_name or "")
    msg = await update.message.reply_text("📊 Generando panel de cartera…")
    data = await portfolio.get_dashboard_data()
    if not data:
        await msg.edit_text(
            "❌ No se pudo obtener el panel. CoinGecko no responde.",
            reply_markup=_back_to_main(),
        )
        return

    try:
        image_bytes = await card_renderer.generate_dashboard_card(data)
    except Exception as e:
        logger.error("Error generando dashboard: %s", e)
        image_bytes = None

    if image_bytes:
        photo = BytesIO(image_bytes)
        photo.name = "dashboard.png"
        caption = (
            f"📊 **Panel de Cartera**\n"
            f"🟠 BTC: {portfolio.format_btc(data.btc_balance)} · "
            f"🔵 USDC: {portfolio.format_usd(data.usdc_balance)}\n"
            f"{data.recommendation}"
        )
        await msg.delete()
        await update.message.reply_photo(
            photo=photo, caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_dashboard"),
                 InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
            ]),
        )
    else:
        text = _dashboard_text(data)
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=_back_to_main())


async def bot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /menu — muestra el menú principal."""
    await update.message.reply_text(
        "🤖 **tokomagraf** · Gestor de Cartera\n\n"
        "💡 Elegí una opción:",
        parse_mode="Markdown",
        reply_markup=_main_menu(),
    )


async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /help — ayuda completa."""
    await update.message.reply_text(
        "📋 **Comandos**\n\n"
        "**📊 Cartera**\n"    "`/start` — Inicio con panel de cartera\n"
            "`/dashboard` — Panel completo de cartera\n"
            "`/comprar <cant> <btc|usdc|usdt> <precio> [fee <monto>]` — Registrar compra\n"
            "`/vender <cant> <btc|usdc|usdt> <precio> [fee <monto>]` — Registrar venta\n"
            "`/swap <cant> <btc|usdc>` — Convertir BTC ↔ USDC al precio de mercado\n"
            "`/simular <comprar|vender> <cant> <asset> <precio> [fee]` — Simular sin ejecutar\n"
            "`/objetivo <porcentaje>` — Fijar objetivo de ganancia (default: 100%)\n"
            "`/trades` — Ver últimos trades\n"
            "`/patrimonio` — Gráfica de evolución de la cartera\n\n"
            "**💰 Mercado**\n"
            "`/precio` — Precio BTC actual\n"
            "`/grafica [días]` — Gráfica de precio (1, 7, 14, 30, 90)\n"
            "`/analisis` — Análisis técnico (SMA, RSI, MACD, tendencia)\n"
            "`/alertas` — Gestionar alertas de precio\n\n"
            "**📥 Importación**\n"
            "`/importar <binance|pionex>` — Importar trades desde CSV\n\n"
            "**🔧 Sistema**\n"
            "`/menu` — Menú principal\n"
            "`/ping` — Verificar que el bot responde\n"
            "`/help` — Esta ayuda\n\n"
            "**Ejemplos:**\n"
            "`/comprar 500usdc` — compra 500 USDC a $1.00\n"
            "`/comprar 0.5 btc 42000` — compra 0.5 BTC\n"
            "`/comprar 1000 usdc 1.00 fee 2.5` — con fee\n"
            "`/comprar 500 usdt 0.999` — USDT\n"
            "`/vender 0.1 btc 85000`\n"
            "`/swap 0.1 btc` — vender BTC por USDC\n"
            "`/swap 100 usdc` — comprar BTC con USDC\n"
            "`/simular comprar 0.5 btc 42000`\n"
            "`/objetivo 200`\n"
            "`/alertas add price_above 100000`\n"
            "`/alertas add profit_target 50`",
        parse_mode="Markdown",
        reply_markup=_back_to_main(),
    )


async def bot_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /ping — verifica que el bot responde."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    await update.message.reply_text(
        f"🏓 Pong! Bot activo — {now}",
        reply_markup=_back_to_main(),
    )


# ── Trades ──────────────────────────────────────────────────

# Regex 1: formato simple "500usdc" o "500 usdc" (sin precio, se asume $1 para stablecoins)
_TRADE_SIMPLE_RE = re.compile(
    r"^(?P<amount>\d+\.?\d*)\s*(?P<asset>usdc|usdt)\s*(?:fee\s+(?P<fee>\d+\.?\d*))?\s*$",
    re.IGNORECASE,
)

# Regex 2: formato completo "0.5 btc 42000" o "0.5 btc 42000 fee 10"
_TRADE_FULL_RE = re.compile(
    r"^(?P<amount>\d+\.?\d*)\s+(?P<asset>btc|usdc|usdt)\s+(?P<price>\d+\.?\d*)(?:\s+fee\s+(?P<fee>\d+\.?\d*))?\s*$",
    re.IGNORECASE,
)


async def bot_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /comprar — registra una compra."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "❌ **Uso:** `/comprar <cantidad> <btc|usdc|usdt> <precio> [fee <monto>]`\n\n"
            "**Formato simple** (stablecoins, asume $1.00):\n"
            "`/comprar 500usdc`\n"
            "`/comprar 200 usdt fee 1`\n\n"
            "**Formato completo** (con precio):\n"
            "`/comprar 0.5 btc 42000`\n"
            "`/comprar 1000 usdc 1.00`\n"
            "`/comprar 0.3 btc 65000 fee 10`",
            parse_mode="Markdown",
        )
        return

    # Intentar formato simple primero (sin precio, asume $1 para stablecoins)
    match = _TRADE_SIMPLE_RE.match(text)
    if match:
        try:
            amount = Decimal(match.group("amount"))
            asset = match.group("asset").upper()
            price = Decimal("1.00")  # stablecoins asumen $1
            fee = Decimal(match.group("fee")) if match.group("fee") else Decimal("0")
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "❌ **Error:** Valores inválidos.",
                parse_mode="Markdown",
            )
            return
        if amount <= 0 or price <= 0 or fee < 0:
            await update.message.reply_text(
                "❌ **Error:** Los valores deben ser positivos.",
                parse_mode="Markdown",
            )
            return
    else:
        # Intentar formato completo (con precio)
        match = _TRADE_FULL_RE.match(text)
        if not match:
            await update.message.reply_text(
                "❌ **Formato inválido.** Usá:\n"
                "`/comprar <cantidad> <btc|usdc|usdt> <precio> [fee <monto>]`\n\n"
                "O para stablecoins:\n"
                "`/comprar <cantidad>usdc` (asume $1.00)\n\n"
                "Ejemplos:\n"
                "`/comprar 500usdc`\n"
                "`/comprar 0.5 btc 42000`",
                parse_mode="Markdown",
            )
            return
        try:
            amount = Decimal(match.group("amount"))
            asset = match.group("asset").upper()
            price = Decimal(match.group("price"))
            fee = Decimal(match.group("fee")) if match.group("fee") else Decimal("0")
            if amount <= 0 or price <= 0 or fee < 0:
                raise ValueError("Valores deben ser positivos")
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "❌ **Error:** Valores inválidos. Verificá los números.\n"
                "Ej: `/comprar 0.5 btc 42000`",
                parse_mode="Markdown",
            )
            return

    # Registrar el trade (tanto para formato simple como completo)
    trade_id = portfolio.register_trade("buy", asset, amount, price, fee)
    if trade_id:
        total_cost = amount * price + fee
        await update.message.reply_text(
            f"✅ **Compra registrada** #{trade_id}\n"
            f"• {portfolio.format_btc(amount) if asset == 'BTC' else portfolio.format_usd(amount)} **{asset}**\n"
            f"• Precio: {portfolio.format_usd(price)} USD\n"
            f"• Costo total: {portfolio.format_usd(total_cost)} USD\n"
            f"{'• Fee: ' + portfolio.format_usd(fee) if fee > 0 else ''}\n\n"
            f"📊 Usá `/dashboard` para ver tu cartera actualizada.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
    else:
        await update.message.reply_text(
            "❌ Error al registrar la compra.",
            reply_markup=_back_to_main(),
        )


async def bot_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /vender — registra una venta."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "❌ **Uso:** `/vender <cantidad> <btc|usdc|usdt> <precio> [fee <monto>]`\n\n"
            "**Formato simple** (stablecoins, asume $1.00):\n"
            "`/vender 100usdc`\n"
            "`/vender 200 usdt fee 1`\n\n"
            "**Formato completo** (con precio):\n"
            "`/vender 0.1 btc 85000`\n"
            "`/vender 0.2 btc 92000 fee 5`",
            parse_mode="Markdown",
        )
        return

    # Intentar formato simple primero (sin precio, asume $1 para stablecoins)
    match = _TRADE_SIMPLE_RE.match(text)
    if match:
        try:
            amount = Decimal(match.group("amount"))
            asset = match.group("asset").upper()
            price = Decimal("1.00")
            fee = Decimal(match.group("fee")) if match.group("fee") else Decimal("0")
        except (InvalidOperation, ValueError):
            await update.message.reply_text("❌ **Error:** Valores inválidos.", parse_mode="Markdown")
            return
        if amount <= 0 or price <= 0 or fee < 0:
            await update.message.reply_text("❌ **Error:** Los valores deben ser positivos.", parse_mode="Markdown")
            return
    else:
        # Intentar formato completo (con precio)
        match = _TRADE_FULL_RE.match(text)
        if not match:
            await update.message.reply_text(
                "❌ **Formato inválido.** Usá:\n"
                "`/vender <cantidad> <btc|usdc|usdt> <precio> [fee <monto>]`\n\n"
                "O para stablecoins:\n"
                "`/vender <cantidad>usdc` (asume $1.00)\n\n"
                "Ej: `/vender 0.1 btc 85000`",
                parse_mode="Markdown",
            )
            return
        try:
            amount = Decimal(match.group("amount"))
            asset = match.group("asset").upper()
            price = Decimal(match.group("price"))
            fee = Decimal(match.group("fee")) if match.group("fee") else Decimal("0")
            if amount <= 0 or price <= 0 or fee < 0:
                raise ValueError("Valores deben ser positivos")
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "❌ **Error:** Valores inválidos. Verificá los números.\n"
                "Ej: `/vender 0.1 btc 85000`",
                parse_mode="Markdown",
            )
            return

    # Verificar balance suficiente
    balance = portfolio.get_asset_balance(asset)
    if balance < amount:
        fmt = portfolio.format_btc if asset == "BTC" else portfolio.format_usd
        await update.message.reply_text(
            f"❌ **Saldo insuficiente.** Tenés {fmt(balance)} {asset}, "
            f"no podés vender {fmt(amount)} {asset}.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return

    trade_id = portfolio.register_trade("sell", asset, amount, price, fee)
    if trade_id:
        total_received = amount * price - fee
        await update.message.reply_text(
            f"✅ **Venta registrada** #{trade_id}\n"
            f"• {portfolio.format_btc(amount) if asset == 'BTC' else portfolio.format_usd(amount)} **{asset}**\n"
            f"• Precio: {portfolio.format_usd(price)} USD\n"
            f"• Recibido: {portfolio.format_usd(total_received)} USD\n"
            f"{'• Fee: ' + portfolio.format_usd(fee) if fee > 0 else ''}\n\n"
            f"📊 Usá `/dashboard` para ver tu cartera actualizada.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
    else:
        await update.message.reply_text(
            "❌ Error al registrar la venta.",
            reply_markup=_back_to_main(),
        )


async def bot_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /trades — lista los últimos trades."""
    trades = portfolio.get_recent_trades(10)
    if not trades:
        await update.message.reply_text(
            "📋 No hay trades registrados todavía.\n\n"
            "Usá `/comprar` para registrar tu primera compra.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return

    lines = ["📋 **Últimos trades:**\n"]
    for t in trades:
        emoji = "🟢" if t.type == "buy" else "🔴"
        asset_icon = "₿" if t.asset == "BTC" else "$"
        amount_str = portfolio.format_btc(t.amount) if t.asset == "BTC" else portfolio.format_usd(t.amount)
        lines.append(
            f"{emoji} `#{t.id}` {asset_icon} {amount_str} **{t.asset}** "
            f"@ {portfolio.format_usd(t.price)}\n"
            f"   _{t.type.capitalize()} · {t.created_at[:16]}_"
            + (f" · fee: {portfolio.format_usd(t.fee)}" if t.fee > 0 else "")
        )
    lines.append(f"\n📊 Total: {len(trades)} trades mostrados")
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=_back_to_main(),
    )


async def bot_swap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /swap — convierte BTC ↔ USDC al precio actual de mercado."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "🔄 **Uso:** `/swap <cantidad> <btc|usdc>`\n\n"
            "Convierte entre BTC y USDC al precio actual de mercado.\n"
            "Ejemplos:\n"
            "`/swap 0.1 btc` — Vende 0.1 BTC por USDC\n"
            "`/swap 100 usdc` — Compra BTC con 100 USDC",
            parse_mode="Markdown",
        )
        return

    # Parsear: <cantidad> <asset>
    swap_re = re.compile(
        r"^(?P<amount>\d+\.?\d*)\s*(?P<asset>btc|usdc|usdt)\s*$",
        re.IGNORECASE,
    )
    match = swap_re.match(text)
    if not match:
        await update.message.reply_text(
            "❌ **Formato inválido.** Usá: `/swap <cantidad> <btc|usdc>`\n"
            "Ej: `/swap 0.1 btc` o `/swap 100 usdc`",
            parse_mode="Markdown",
        )
        return

    try:
        amount = Decimal(match.group("amount"))
        asset = match.group("asset").upper()
    except (InvalidOperation, ValueError):
        await update.message.reply_text("❌ **Error:** Cantidad inválida.", parse_mode="Markdown")
        return

    if amount <= 0:
        await update.message.reply_text("❌ **Error:** La cantidad debe ser positiva.", parse_mode="Markdown")
        return

    # Obtener precio actual de BTC
    msg = await update.message.reply_text("🔄 Obteniendo precio actual para el swap…")
    price_data = await portfolio.fetch_btc_price()
    if not price_data:
        await msg.edit_text("❌ No se pudo obtener el precio de BTC. Intenta de nuevo.")
        return

    btc_price = price_data.price_usd

    if asset == "BTC":
        # Vender BTC -> recibir USDC
        amount_btc = amount
        amount_usdc = (amount_btc * btc_price).quantize(Decimal("0.01"))

        balance_btc = portfolio.get_btc_balance()
        if balance_btc < amount_btc:
            await msg.edit_text(
                f"❌ **Saldo insuficiente.** Tenés {portfolio.format_btc(balance_btc)} BTC, "
                f"no podés vender {portfolio.format_btc(amount_btc)} BTC.",
                parse_mode="Markdown",
            )
            return

        # Ejecutar swap como venta de BTC + compra de USDC
        portfolio.register_trade("sell", "BTC", amount_btc, btc_price)
        portfolio.register_trade("buy", "USDC", amount_usdc, Decimal("1.00"))

        await msg.edit_text(
            f"🔄 **Swap ejecutado** ✅\n\n"
            f"• Vendiste {portfolio.format_btc(amount_btc)} **BTC**\n"
            f"• Recibiste {portfolio.format_usd(amount_usdc)} **USDC**\n"
            f"• Precio: {portfolio.format_usd(btc_price)}\n\n"
            f"📊 Usá `/dashboard` para ver tu cartera actualizada.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )

    elif asset in ("USDC", "USDT"):
        # Comprar BTC con USDC/USDT
        amount_stable = amount
        amount_btc = (amount_stable / btc_price).quantize(Decimal("0.00000001"))

        balance_stable = portfolio.get_asset_balance(asset)
        if balance_stable < amount_stable:
            symbol = "USDC" if asset == "USDC" else "USDT"
            await msg.edit_text(
                f"❌ **Saldo insuficiente.** Tenés {portfolio.format_usd(balance_stable)} {symbol}, "
                f"no podés convertir {portfolio.format_usd(amount_stable)} {symbol}.",
                parse_mode="Markdown",
            )
            return

        # Ejecutar swap como venta de stablecoin + compra de BTC
        portfolio.register_trade("sell", asset, amount_stable, Decimal("1.00"))
        portfolio.register_trade("buy", "BTC", amount_btc, btc_price)

        await msg.edit_text(
            f"🔄 **Swap ejecutado** ✅\n\n"
            f"• Convertiste {portfolio.format_usd(amount_stable)} **{asset}**\n"
            f"• Compraste {portfolio.format_btc(amount_btc)} **BTC**\n"
            f"• Precio: {portfolio.format_usd(btc_price)}\n\n"
            f"📊 Usá `/dashboard` para ver tu cartera actualizada.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )


async def bot_simular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /simular — simula una compra/venta sin ejecutarla."""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "🧮 **Uso:** `/simular <comprar|vender> <cantidad> <btc|usdc|usdt> <precio> [fee <monto>]`\n\n"
            "Ejemplos:\n"
            "`/simular comprar 0.5 btc 42000`\n"
            "`/simular vender 0.1 btc 85000 fee 5`\n"
            "`/simular comprar 1000 usdc 1.00`\n\n"
            "💡 El precio es opcional para stablecoins (asume $1.00).",
            parse_mode="Markdown",
        )
        return

    # Parsear: <comprar|vender> <cantidad> <asset> [precio] [fee <monto>]
    sim_re = re.compile(
        r"^(?P<action>comprar|vender)\s+"
        r"(?P<amount>\d+\.?\d*)\s+(?P<asset>btc|usdc|usdt)"
        r"(?:\s+(?P<price>\d+\.?\d*))?"
        r"(?:\s+fee\s+(?P<fee>\d+\.?\d*))?"
        r"\s*$",
        re.IGNORECASE,
    )
    match = sim_re.match(text)
    if not match:
        await update.message.reply_text(
            "❌ **Formato inválido.** Usá: `/simular <comprar|vender> <cantidad> <asset> <precio>`\n"
            "Ej: `/simular comprar 0.5 btc 42000`",
            parse_mode="Markdown",
        )
        return

    try:
        action = match.group("action").lower()
        amount = Decimal(match.group("amount"))
        asset = match.group("asset").upper()
        price_str = match.group("price")
        fee_str = match.group("fee")

        price = Decimal(price_str) if price_str else None
        fee = Decimal(fee_str) if fee_str else Decimal("0")

        if amount <= 0 or fee < 0:
            raise ValueError("Valores inválidos")
        if price is not None and price <= 0:
            raise ValueError("Precio inválido")

        # Si no hay precio, usar precio actual de BTC o $1 para stablecoins
        if price is None:
            if asset == "BTC":
                price_data = await portfolio.fetch_btc_price()
                if not price_data:
                    await update.message.reply_text(
                        "❌ No se pudo obtener el precio actual de BTC. Especificá el precio manualmente.",
                    )
                    return
                price = price_data.price_usd
            else:
                price = Decimal("1.00")

        trade_type = "buy" if action == "comprar" else "sell"
        result = portfolio.simulate_trade(trade_type, asset, amount, price, fee)

        if not result:
            await update.message.reply_text(
                "❌ **Error en la simulación.** Verificá los datos ingresados.",
                parse_mode="Markdown",
            )
            return

        text_output = portfolio.format_simulation(result, action)
        await update.message.reply_text(
            text_output,
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )

    except (InvalidOperation, ValueError) as e:
        await update.message.reply_text(
            f"❌ **Error:** Valores inválidos. {e}",
            parse_mode="Markdown",
        )


async def bot_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /objetivo — fija el porcentaje de ganancia objetivo."""
    if not context.args:
        current = portfolio.get_config("target_pct", "100")
        await update.message.reply_text(
            f"🎯 **Objetivo actual:** +{current}%\n\n"
            f"Usá `/objetivo <porcentaje>` para cambiarlo.\n"
            f"Ej: `/objetivo 200` → objetivo de +200% sobre precio medio de compra.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return

    try:
        pct = int(context.args[0])
        if pct < 10 or pct > 1000:
            await update.message.reply_text(
                "❌ El porcentaje debe estar entre 10% y 1000%.",
                reply_markup=_back_to_main(),
            )
            return

        portfolio.set_config("target_pct", str(pct))
        await update.message.reply_text(
            f"✅ **Objetivo actualizado:** +{pct}%\n\n"
            f"El precio objetivo ahora será {pct}% sobre tu precio medio de compra.\n"
            f"Usá `/dashboard` para ver el cambio.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Usá: `/objetivo <porcentaje>`\n"
            "Ej: `/objetivo 200`",
            parse_mode="Markdown",
        )


# ── Precio BTC ─────────────────────────────────────────────


async def btc_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /precio — genera tarjeta visual con precio de BTC."""
    msg = await update.message.reply_text("🔍 Obteniendo precio BTC…")

    detail = await portfolio.fetch_btc_price_detail()
    if not detail:
        price = await portfolio.fetch_btc_price()
        if price:
            await msg.edit_text(
                f"💰 **Bitcoin (BTC)**\n\n"
                f"Precio: **{portfolio.format_usd(price.price_usd)}** USD\n"
                f"🕐 {price.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"*Fuente: CoinGecko*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
        else:
            await msg.edit_text(
                "❌ No se pudo obtener el precio de BTC. Intenta de nuevo.",
                reply_markup=_back_to_main(),
            )
        return

    try:
        image_bytes = await card_renderer.generate_price_card(
            price_usd=detail.price_usd,
            change_24h_pct=detail.change_24h_pct,
            high_24h=detail.high_24h,
            low_24h=detail.low_24h,
        )
    except Exception as e:
        logger.error("Error generando tarjeta precio: %s", e)
        image_bytes = None

    if image_bytes:
        photo = BytesIO(image_bytes)
        photo.name = "btc_price.png"

        caption = (
            f"💰 **Bitcoin** — ${detail.price_usd:,.2f} USD"
            + (
                f"  {'📈' if (detail.change_24h_pct or 0) >= 0 else '📉'}"
                f" {detail.change_24h_pct:+.2f}%"
                if detail.change_24h_pct is not None
                else ""
            )
        )

        await msg.delete()
        await update.message.reply_photo(
            photo=photo, caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                 InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
            ]),
        )
    else:
        await msg.edit_text(
            f"💰 **Bitcoin (BTC)**\n\n"
            f"Precio: **{portfolio.format_usd(detail.price_usd)}** USD\n"
            + (
                f"📊 24h: {detail.change_24h_pct:+.2f}%\n"
                if detail.change_24h_pct is not None
                else ""
            )
            + f"🕐 {detail.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"*Fuente: CoinGecko*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                 InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
            ]),
        )


async def bot_analisis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /analisis — análisis técnico completo de BTC."""
    msg = await update.message.reply_text("📊 Calculando análisis técnico…")

    analysis = await portfolio.calculate_technical_analysis()
    if not analysis:
        await msg.edit_text(
            "❌ No hay suficientes datos históricos para el análisis. "
            "Intentá de nuevo más tarde.",
            reply_markup=_back_to_main(),
        )
        return

    # Parsear días para la gráfica técnica
    days = 90
    if context.args:
        try:
            d = int(context.args[0])
            if d in (7, 14, 30, 90):
                days = d
        except ValueError:
            pass
    chart_path = await portfolio.generate_technical_chart_async(days)

    text_output = portfolio.format_analysis_text(analysis)

    if chart_path:
        try:
            with open(chart_path, "rb") as f:
                await msg.delete()
                await update.message.reply_photo(
                    photo=f,
                    caption=f"📊 **Análisis Técnico BTC** — {days} días",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_analisis"),
                         InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                    ]),
                )
                # Enviar el texto del análisis como reply
                await update.message.reply_text(
                    text_output,
                    parse_mode="Markdown",
                    reply_markup=_back_to_main(),
                )
        except Exception as e:
            logger.error("Error enviando gráfica análisis: %s", e)
            await msg.edit_text(text_output, parse_mode="Markdown", reply_markup=_back_to_main())
    else:
        await msg.edit_text(text_output, parse_mode="Markdown", reply_markup=_back_to_main())


async def bot_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /alertas — gestiona alertas de precio."""
    if not context.args:
        alerts = portfolio.get_all_alerts()
        text = portfolio.format_alert_list(alerts)
        text += (
            "\n\n**Comandos:**\n"
            "`/alertas add price_above <precio>` — Alerta cuando BTC suba de\n"
            "`/alertas add price_below <precio>` — Alerta cuando BTC baje de\n"
            "`/alertas add profit_target <%>` — Alerta cuando ganancia llegue a %\n"
            "`/alertas add loss_limit <%>` — Alerta cuando pérdida llegue a %\n"
            "`/alertas del <id>` — Eliminar alerta\n"
            "`/alertas clear` — Eliminar todas"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_back_to_main())
        return

    if context.args[0] == "add" and len(context.args) >= 3:
        alert_type = context.args[1].lower()
        try:
            target = Decimal(context.args[2])
        except (InvalidOperation, ValueError):
            await update.message.reply_text(
                "❌ Valor objetivo inválido.", parse_mode="Markdown"
            )
            return

        note = " ".join(context.args[3:]) if len(context.args) > 3 else ""

        alert_id = portfolio.create_alert(alert_type, target, note=note)
        if alert_id:
            await update.message.reply_text(
                f"✅ **Alerta creada** #{alert_id}\n"
                f"• Tipo: {alert_type}\n"
                f"• Objetivo: {target!s}\n"
                + (f"• Nota: {note}\n" if note else "")
                + "\nRecibirás una notificación cuando se active.",
                parse_mode="Markdown",
                reply_markup=_back_to_main(),
            )
        else:
            await update.message.reply_text(
                "❌ Error al crear la alerta. Tipos válidos: "
                "price_above, price_below, profit_target, loss_limit",
                parse_mode="Markdown",
            )
        return

    if context.args[0] == "del" and len(context.args) >= 2:
        try:
            alert_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text(
                "❌ ID inválido. Usá: `/alertas del <id>`", parse_mode="Markdown"
            )
            return
        if portfolio.delete_alert(alert_id):
            await update.message.reply_text(
                f"🗑️ Alerta #{alert_id} eliminada.",
                reply_markup=_back_to_main(),
            )
        else:
            await update.message.reply_text(
                f"❌ Alerta #{alert_id} no encontrada.",
                reply_markup=_back_to_main(),
            )
        return

    if context.args[0] == "clear":
        alerts = portfolio.get_all_alerts()
        for a in alerts:
            portfolio.delete_alert(a.id)
        await update.message.reply_text(
            "🗑️ Todas las alertas han sido eliminadas.",
            reply_markup=_back_to_main(),
        )
        return

    await update.message.reply_text(
        "❌ **Uso:**\n"
        "`/alertas` — Listar alertas\n"
        "`/alertas add price_above <precio>` — Nueva alerta\n"
        "`/alertas del <id>` — Eliminar alerta\n"
        "`/alertas clear` — Eliminar todas",
        parse_mode="Markdown",
    )


async def bot_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /importar — importa trades desde CSV."""
    if not context.args:
        await update.message.reply_text(
            "📥 **Uso:** `/importar <binance|pionex>`\n\n"
            "Envía el contenido CSV como mensaje de respuesta o en un bloque de código.\n\n"
            "**Pasos:**\n"
            "1. Exportá tus trades desde Binance o Pionex como CSV\n"
            "2. Usá `/importar binance` seguido del contenido CSV\n"
            "3. Revisá los trades importados con `/trades`\n\n"
            "*Formatos soportados: Binance (Trade History), Pionex (Order History)*",
            parse_mode="Markdown",
        )
        return

    platform = context.args[0].lower()
    if platform not in ("binance", "pionex"):
        await update.message.reply_text(
            "❌ Plataforma no soportada. Usá `binance` o `pionex`.",
            parse_mode="Markdown",
        )
        return

    csv_content = ""
    if len(context.args) > 1:
        csv_content = " ".join(context.args[1:])
    elif update.message.reply_to_message and update.message.reply_to_message.text:
        csv_content = update.message.reply_to_message.text

    if not csv_content or len(csv_content) < 20:
        await update.message.reply_text(
            "❌ No se encontró contenido CSV. "
            "Respondé a un mensaje con el CSV o incluí el contenido directamente.",
        )
        return

    msg = await update.message.reply_text("📥 Importando trades…")

    imported, errors = portfolio.import_trades_from_csv(
        csv_content, platform, filename=f"{platform}_import.csv"
    )

    if imported > 0:
        await msg.edit_text(
            f"✅ **Importación completada**\n"
            f"• {imported} trades importados desde {platform.capitalize()}\n"
            + (f"• {errors} errores\n" if errors else "")
            + "\n📊 Usá `/trades` para ver los trades importados.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
    else:
        await msg.edit_text(
            f"❌ No se pudieron importar trades. "
            + (f"({errors} errores de formato)" if errors else "Verificá el formato del CSV."),
            reply_markup=_back_to_main(),
        )


async def bot_patrimonio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /patrimonio — muestra la evolución del patrimonio."""
    msg = await update.message.reply_text("📊 Generando gráfica de evolución…")

    chart_path = await portfolio.generate_portfolio_evolution_chart_async()

    if chart_path is None:
        await msg.edit_text(
            "❌ No hay suficientes datos históricos. "
            "Usá `/dashboard` regularmente para acumular datos diarios.",
            reply_markup=_back_to_main(),
        )
        return

    try:
        with open(chart_path, "rb") as f:
            await msg.delete()
            await update.message.reply_photo(
                photo=f,
                caption=f"💰 **Evolución del Patrimonio** — Cartera completa",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_patrimonio"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
    except Exception as e:
        logger.error("Error enviando gráfica patrimonio: %s", e)
        await msg.edit_text(
            "❌ Error al generar la gráfica.",
            reply_markup=_back_to_main(),
        )


async def btc_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /grafica — genera imagen con gráfica de precio BTC."""
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
            if days not in (1, 7, 14, 30, 90):
                days = 7
        except ValueError:
            days = 7

    msg = await update.message.reply_text("📊 Generando gráfica BTC…")

    chart_path = await portfolio.generate_btc_chart_async(days)

    if chart_path is None:
        await msg.edit_text(
            "❌ No se pudo generar la gráfica. Intenta de nuevo.",
            reply_markup=_back_to_main(),
        )
        return

    try:
        with open(chart_path, "rb") as f:
            await msg.delete()
            await update.message.reply_photo(
                photo=f,
                caption=f"📊 **BTC/USD** — Gráfica de los últimos {days} días",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_grafica"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
    except Exception as e:
        logger.error("Error enviando gráfica: %s", e)
        await msg.edit_text(
            "❌ Error al enviar la gráfica.",
            reply_markup=_back_to_main(),
        )


# ═════════════════════════════════════════════════════════════
#  Callback handler
# ═════════════════════════════════════════════════════════════


async def _reply_or_edit(query, text: str, parse_mode: Optional[str] = None, reply_markup=None) -> None:
    if query.message.photo:
        await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja los callbacks del menú."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav_main":
        await query.message.reply_text(
            "🤖 **tokomagraf** · Gestor de Cartera\n\n💡 Elegí una opción:",
            parse_mode="Markdown",
            reply_markup=_main_menu(),
        )
        return

    if data == "nav_dashboard":
        await _reply_or_edit(query, "📊 Generando panel de cartera…", parse_mode="Markdown")

        pdata = await portfolio.get_dashboard_data()
        if not pdata:
            await _reply_or_edit(
                query, "❌ No se pudo obtener el panel. CoinGecko no responde.",
                reply_markup=_back_to_main(),
            )
            return

        try:
            image_bytes = await card_renderer.generate_dashboard_card(pdata)
        except Exception as e:
            logger.error("Error en callback dashboard: %s", e)
            image_bytes = None

        if image_bytes:
            photo = BytesIO(image_bytes)
            photo.name = "dashboard.png"
            caption = (
                f"📊 **Panel de Cartera**\n"
                f"🟠 BTC: {portfolio.format_btc(pdata.btc_balance)} · "
                f"🔵 USDC: {portfolio.format_usd(pdata.usdc_balance)}\n"
                f"{pdata.recommendation}"
            )
            await query.message.reply_photo(
                photo=photo, caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_dashboard"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
            # Mensaje de confirmación
            if not query.message.photo:
                await _reply_or_edit(
                    query, "📊 **Panel de Cartera** — generado ✅",
                    parse_mode="Markdown",
                    reply_markup=_back_to_main(),
                )
        else:
            text = _dashboard_text(pdata)
            await _reply_or_edit(
                query, text, parse_mode="Markdown", reply_markup=_back_to_main(),
            )
        return

    if data == "nav_grafica":
        await _reply_or_edit(query, "📊 Generando gráfica BTC…", parse_mode="Markdown")

        chart_path = await portfolio.generate_btc_chart_async(7)
        if chart_path is None:
            await _reply_or_edit(
                query, "❌ No se pudo generar la gráfica.",
                reply_markup=_back_to_main(),
            )
            return

        try:
            with open(chart_path, "rb") as f:
                await query.message.reply_photo(
                    photo=f,
                    caption="📊 **BTC/USD** — Gráfica de los últimos 7 días",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_grafica"),
                         InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                    ]),
                )
                if not query.message.photo:
                    await _reply_or_edit(
                        query, "📊 **Gráfica BTC** — generada ✅",
                        parse_mode="Markdown",
                        reply_markup=_back_to_main(),
                    )
        except Exception as e:
            logger.error("Error en callback gráfica: %s", e)
            await _reply_or_edit(query, "❌ Error al generar la gráfica.", reply_markup=_back_to_main())
        return

    if data == "nav_precio":
        await _reply_or_edit(query, "🔍 Obteniendo precio BTC…", parse_mode="Markdown")

        detail = await portfolio.fetch_btc_price_detail()
        if not detail:
            price = await portfolio.fetch_btc_price()
            if price:
                await _reply_or_edit(
                    query,
                    f"💰 **Bitcoin (BTC)**\n\n"
                    f"Precio: **{portfolio.format_usd(price.price_usd)}** USD\n"
                    f"🕐 {price.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                    f"*Fuente: CoinGecko*",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                         InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                    ]),
                )
            else:
                await _reply_or_edit(
                    query, "❌ No se pudo obtener el precio de BTC.",
                    reply_markup=_back_to_main(),
                )
            return

        try:
            image_bytes = await card_renderer.generate_price_card(
                price_usd=detail.price_usd,
                change_24h_pct=detail.change_24h_pct,
                high_24h=detail.high_24h,
                low_24h=detail.low_24h,
            )
        except Exception as e:
            logger.error("Error generando tarjeta precio: %s", e)
            image_bytes = None

        if image_bytes:
            photo = BytesIO(image_bytes)
            photo.name = "btc_price.png"
            caption = (
                f"💰 **Bitcoin** — ${detail.price_usd:,.2f} USD"
                + (
                    f"  {'📈' if (detail.change_24h_pct or 0) >= 0 else '📉'}"
                    f" {detail.change_24h_pct:+.2f}%"
                    if detail.change_24h_pct is not None
                    else ""
                )
            )
            await query.message.reply_photo(
                photo=photo, caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
            if not query.message.photo:
                await _reply_or_edit(
                    query, "💰 **Precio BTC** — imagen generada ✅",
                    parse_mode="Markdown",
                    reply_markup=_back_to_main(),
                )
        else:
            await _reply_or_edit(
                query,
                f"💰 **Bitcoin (BTC)**\n\n"
                f"Precio: **{portfolio.format_usd(detail.price_usd)}** USD\n"
                f"📊 24h: {detail.change_24h_pct:+.2f}%\n"
                f"🕐 {detail.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"*Fuente: CoinGecko*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_precio"),
                     InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                ]),
            )
        return

    if data == "nav_analisis":
        await _reply_or_edit(query, "📊 Generando análisis técnico…", parse_mode="Markdown")
        analysis = await portfolio.calculate_technical_analysis()
        if not analysis:
            await _reply_or_edit(query, "❌ No hay suficientes datos históricos.", reply_markup=_back_to_main())
            return
        text = portfolio.format_analysis_text(analysis)
        await _reply_or_edit(query, text, parse_mode="Markdown", reply_markup=_back_to_main())
        return

    if data == "nav_patrimonio":
        await _reply_or_edit(query, "📊 Generando gráfica de evolución…", parse_mode="Markdown")
        chart_path = await portfolio.generate_portfolio_evolution_chart_async()
        if chart_path:
            try:
                with open(chart_path, "rb") as f:
                    await query.message.reply_photo(
                        photo=f,
                        caption="💰 **Evolución del Patrimonio**",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Actualizar", callback_data="nav_patrimonio"),
                             InlineKeyboardButton("🏠 Menú", callback_data="nav_main")],
                        ]),
                    )
            except Exception as e:
                logger.error("Error en callback patrimonio: %s", e)
                await _reply_or_edit(query, "❌ Error al generar la gráfica.", reply_markup=_back_to_main())
        else:
            await _reply_or_edit(query, "❌ No hay suficientes datos históricos.", reply_markup=_back_to_main())
        return

    if data == "nav_alertas":
        alerts = portfolio.get_all_alerts()
        text = portfolio.format_alert_list(alerts)
        await query.message.reply_text(
            text + "\n\nUsá `/alertas` para gestionar tus alertas.",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return

    if data == "nav_swap":
        await query.message.reply_text(
            "🔄 **Swap BTC ↔ USDC**\n\n"
            "Usá `/swap <cantidad> <btc|usdc>` para convertir.\n\n"
            "Ejemplos:\n"
            "`/swap 0.1 btc` — Vende BTC por USDC\n"
            "`/swap 100 usdc` — Compra BTC con USDC",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return

    if data == "nav_ayuda":
        await query.message.reply_text(
            "📋 **Comandos**\n\n"
            "**📊 Cartera**\n"
            "`/start` — Inicio con panel de cartera\n"
            "`/dashboard` — Panel completo\n"
            "`/comprar <cant> <btc|usdc|usdt> <precio> [fee]` — Comprar\n"
            "`/vender <cant> <btc|usdc|usdt> <precio> [fee]` — Vender\n"
            "`/swap <cant> <btc|usdc>` — Convertir BTC ↔ USDC\n"
            "`/simular <comprar|vender> <cant> <asset> <precio> [fee]` — Simular\n"
            "`/objetivo <porcentaje>` — Fijar objetivo\n"
            "`/trades` — Ver últimos trades\n"
            "`/patrimonio` — Evolución del patrimonio\n\n"
            "**💰 Mercado**\n"
            "`/precio` — Precio BTC\n"
            "`/grafica [días]` — Gráfica (1, 7, 14, 30, 90)\n"
            "`/analisis` — Análisis técnico (SMA, RSI, MACD)\n"
            "`/alertas` — Alertas de precio\n\n"
            "**📥 Importación**\n"
            "`/importar <binance|pionex>` — Importar trades CSV\n\n"
            "**🔧 Sistema**\n"
            "`/menu` — Menú\n"
            "`/ping` — Ping\n"
            "`/help` — Ayuda",
            parse_mode="Markdown",
            reply_markup=_back_to_main(),
        )
        return


# ═════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════


async def post_init(application: Application) -> None:
    """Inicializa la base de datos al arrancar."""
    try:
        portfolio.init_db()
        logger.info("✅ Base de datos inicializada correctamente")
    except Exception as e:
        logger.error("❌ Error inicializando base de datos: %s", e)


def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN no configurado.")
        return

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Cartera
    app.add_handler(CommandHandler("start", bot_start))
    app.add_handler(CommandHandler("dashboard", bot_dashboard))
    app.add_handler(CommandHandler("menu", bot_menu))
    app.add_handler(CommandHandler("comprar", bot_buy))
    app.add_handler(CommandHandler("vender", bot_sell))
    app.add_handler(CommandHandler("trades", bot_trades))
    app.add_handler(CommandHandler("objetivo", bot_target))
    app.add_handler(CommandHandler("swap", bot_swap))
    app.add_handler(CommandHandler("simular", bot_simular))

    # Mercado
    app.add_handler(CommandHandler("precio", btc_price))
    app.add_handler(CommandHandler("grafica", btc_chart))
    app.add_handler(CommandHandler("analisis", bot_analisis))
    app.add_handler(CommandHandler("alertas", bot_alertas))

    # Importación
    app.add_handler(CommandHandler("importar", bot_importar))

    # Patrimonio
    app.add_handler(CommandHandler("patrimonio", bot_patrimonio))

    # Sistema
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("ping", bot_ping))

    # Background job: check alerts every 5 minutes
    app.job_queue.run_repeating(
        check_alerts_background,
        interval=300,  # cada 5 minutos
        first=30,      # primera ejecución a los 30 segundos
    )

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(nav_)"))

    logger.info("🤖 tokomagraf Gestor de Cartera iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
