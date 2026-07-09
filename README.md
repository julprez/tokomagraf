# 🪙 tokomagraf — Gestor de Cartera Cripto BTC

<p align="center">
  <img src="https://img.shields.io/badge/status-stable-success?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white&style=flat-square" alt="Docker">
</p>

**tokomagraf** es una aplicación web para gestionar tu cartera de Bitcoin. Registrá operaciones, visualizá gráficos, simulá escenarios, compará tu estrategia contra DCA, y recibí predicciones de mercado — todo en un dashboard dark mode responsive.

---

## ✨ Funcionalidades

| Categoría | Features |
|---|---|
| **Dashboard** | Patrimonio en USD/BTC/USDC, gráfico 7d con toggle Portfolio/BTC, zonas ganancia/pérdida, ranking volatilidad |
| **Operaciones** | Compra, venta, depósito, retiro de BTC/USDC/EUR con cálculo automático y **notas de trading** |
| **Historial** | 7 gráficos interactivos (evolución, P&L, coste medio, rentabilidad mensual) + export **CSV** |
| **Análisis** | RSI, MACD, SMA 50/200, soporte/resistencia, Golden/Death Cross |
| **Predicción** | Score 0-100% combinando 8 indicadores (RSI, MACD, Fear & Greed, dominancia BTC, etc.) |
| **DCA** | Comparativa tu estrategia vs DCA automático + **insights de IA** |
| **Simulador** | Proyectá tu cartera a cualquier precio BTC, con sugerencias de compra/venta y gráfico comparativo |
| **Alertas** | Precio objetivo, profit target %, stop loss. Notificaciones con badge |
| **Vista fiscal** | P&L realizado por año (FIFO simplificado) |
| **Autenticación** | Seed phrase de 6 palabras (estilo wallet) + email/password tradicional |

---

## 🚀 Instalación (un comando)

```bash
curl -sSL https://raw.githubusercontent.com/TU-USUARIO/tokomagraf/main/install-remote.sh | bash
```

El instalador automáticamente:
- Instala Docker si no está
- Genera contraseñas seguras
- Te pregunta si tenés dominio (HTTPS con Let's Encrypt)
- Abre puertos en el firewall
- Construye e inicia los 6 servicios
- Configura **backup diario** de la base de datos

### Sin dominio
Si no tenés dominio, el instalador funciona igual con HTTP en la IP del VPS.

### Manual (desarrollo)
```bash
git clone https://github.com/TU-USUARIO/tokomagraf.git
cd tokomagraf
docker compose -f docker-compose.dev.yml up -d
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────┐
│                    Internet                      │
│                      │                           │
│              ┌───────▼───────┐                   │
│              │    Caddy       │  SSL/HTTPS       │
│              │  (reverse      │  Let's Encrypt   │
│              │   proxy)       │                   │
│              └───────┬───────┘                   │
│                      │                           │
│  ┌───────────────────┼───────────────────────┐   │
│  │            Docker Network                   │   │
│  │                   │                         │   │
│  │  ┌────────────┐   │   ┌────────────────┐   │   │
│  │  │  Frontend   │   │   │    Backend     │   │   │
│  │  │  Nginx      │───┼──▶│    FastAPI     │   │   │
│  │  │  React SPA  │   │   │    :8000       │   │   │
│  │  └────────────┘   │   └───────┬────────┘   │   │
│  │                   │           │             │   │
│  │                   │   ┌───────┴────────┐   │   │
│  │                   │   │    Worker       │   │   │
│  │                   │   │    Celery       │   │   │
│  │                   │   └───────┬────────┘   │   │
│  │                   │           │             │   │
│  │              ┌────┴───┐  ┌───┴────┐         │   │
│  │              │  Redis  │  │  PG 16 │         │   │
│  │              └────────┘  └────────┘         │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack

| Capa | Tecnología |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Recharts, React Query, React Router |
| **Backend** | FastAPI, SQLAlchemy, Celery, slowapi, pandas |
| **DB** | PostgreSQL 16 |
| **Cache/Queue** | Redis 7 |
| **Reverse Proxy** | Caddy (SSL automático) |
| **Infra** | Docker Compose, Nginx |

---

## 📁 Estructura del proyecto

```
tokomagraf/
├── frontend/              # React + Vite + Tailwind
│   ├── src/
│   │   ├── pages/         # Dashboard, Operations, History, DCA, etc.
│   │   ├── components/    # Layout, Toast, Skeleton, EmptyState
│   │   └── api/           # Cliente HTTP (axios)
│   └── Dockerfile
├── backend/               # FastAPI
│   ├── app/
│   │   ├── api/           # Endpoints REST
│   │   ├── services/      # Lógica de negocio
│   │   ├── models/        # SQLAlchemy models
│   │   └── tasks/         # Celery workers
│   └── Dockerfile
├── docker-compose.yml         # Desarrollo
├── docker-compose.prod.yml    # Producción (Caddy + SSL)
├── docker-compose.dev.yml     # Desarrollo (hot-reload)
├── Caddyfile                  # Configuración SSL
├── install.sh                 # Instalador interactivo
├── install-remote.sh          # Instalador remoto (curl | bash)
├── backup.sh                  # Backup diario PostgreSQL
└── .env.example               # Template de variables
```

---

## 📦 Comandos útiles

```bash
# Producción
docker compose -f docker-compose.prod.yml up -d      # Iniciar
docker compose -f docker-compose.prod.yml logs -f     # Ver logs
docker compose -f docker-compose.prod.yml down        # Detener

# Desarrollo
docker compose -f docker-compose.dev.yml up -d        # Iniciar con hot-reload

# Backup
bash backup.sh                                        # Backup manual
crontab -l | grep backup                              # Ver cron de backup
```

---

## 🔒 Seguridad

- **Rate limiting**: 200 req/min global (slowapi)
- **Security headers**: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **CORS**: configurable por dominio
- **Autenticación**: JWT + seed phrase (6 palabras)
- **SSL**: automático con Let's Encrypt (Caddy)
- **Healthchecks**: todos los servicios con autoreinicio

---

## 📄 Licencia

MIT — hacé lo que quieras con el código. Si lo usás, ¡compartí tus mejoras!

---

<p align="center">
  <sub>Hecho con ₿ en Argentina</sub>
</p>
