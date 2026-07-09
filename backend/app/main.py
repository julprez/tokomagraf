# =============================================================
# main.py — FastAPI Application
# =============================================================

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import init_db
from app.api.rate_limit import setup_rate_limit, limiter
from app.api.auth import router as auth_router
from app.api.operations import router as operations_router
from app.api.prices import router as prices_router
from app.api.portfolio_api import router as portfolio_router
from app.api.alerts import router as alerts_router
from app.api.exchanges_api import router as exchanges_router
from app.api.notifications import router as notifications_router
from app.api.predictions import router as predictions_router
from app.api.dca import router as dca_router

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tokomagraf_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("🚀 Iniciando tokomagraf API…")
    try:
        await init_db()
        logger.info("✅ Base de datos inicializada")
    except Exception as e:
        logger.error("❌ Error inicializando BD: %s", e)
    yield
    logger.info("🛑 tokomagraf API detenida")


app = FastAPI(
    title="tokomagraf API",
    description="Gestor de cartera cripto — API REST",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate Limiting
setup_rate_limit(app)

# CORS — soporta IP y dominio para producción
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
# Si es un dominio sin protocolo, agregar https://
if FRONTEND_URL and "://" not in FRONTEND_URL:
    FRONTEND_URL = f"https://{FRONTEND_URL}"
allowed_origins = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:5173",
]
# Agregar variante http si el dominio usa https
if FRONTEND_URL.startswith("https://"):
    allowed_origins.append(FRONTEND_URL.replace("https://", "http://"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers with rate limiting
app.include_router(auth_router)
app.include_router(operations_router)
app.include_router(prices_router)
app.include_router(portfolio_router)
app.include_router(alerts_router)
app.include_router(exchanges_router)
app.include_router(notifications_router)
app.include_router(predictions_router)
app.include_router(dca_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
