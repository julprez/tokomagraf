# Especificación del Proyecto: Gestor de Portafolio BTC

## Objetivo

Crear una aplicación web dockerizada para gestionar inversiones en
Bitcoin, con seguimiento del portafolio, estadísticas, gráficos y apoyo
a la toma de decisiones.

## Funcionalidades principales

-   Registro de compras, ventas, depósitos y retiradas.
-   Conversión BTC ↔ USDC.
-   Capital invertido.
-   BTC acumulado.
-   USDC disponible.
-   Precio medio de compra.
-   Valor actual del portafolio.
-   Ganancia/pérdida diaria.
-   Ganancia total desde la primera inversión.
-   Rentabilidad porcentual.
-   Registro de comisiones.
-   Historial completo de operaciones.
-   Simulador de compra y venta.
-   Alertas de precio.
-   Integración con APIs de exchanges.
-   Importación mediante CSV.

## Panel principal

-   Patrimonio total.
-   BTC acumulados.
-   Precio medio.
-   Precio actual.
-   Ganancia diaria.
-   Ganancia total.
-   Rentabilidad.
-   Capital aportado.
-   USDC disponible.

## Arquitectura

``` text
Internet
    │
Nginx / Traefik
    │
 ├── Frontend (React + TypeScript)
 ├── Backend (FastAPI)
 ├── PostgreSQL
 ├── Redis
 └── Worker
```

## Frontend

-   React + TypeScript
-   Vite
-   Tailwind CSS
-   React Router
-   React Query
-   React Hook Form
-   Zod
-   Recharts

### Pantallas

-   Dashboard
-   Operaciones
-   Historial
-   Estadísticas
-   Configuración
-   Alertas

## Backend

### Tecnologías

-   FastAPI
-   SQLAlchemy
-   Alembic
-   Pydantic
-   Celery/RQ (tareas)
-   JWT

### Estructura

``` text
app/
  api/
  services/
  models/
  repositories/
  schemas/
  auth/
  indicators/
  exchanges/
  database/
  tasks/
```

### Servicios

-   PortfolioService
-   OperationService
-   StatisticsService
-   IndicatorService
-   PredictionService
-   PriceService
-   ExchangeService

## Base de datos

### users

-   id
-   nombre
-   email
-   password
-   created_at

### exchanges

-   id
-   nombre
-   api_key
-   secret

### assets

-   BTC
-   USDC
-   EUR

### operations

-   id
-   tipo
-   activo
-   cantidad
-   precio
-   comisión
-   fecha

### portfolio

-   btc_actual
-   usdc_actual
-   eur_actual
-   capital_aportado
-   beneficio_total

### daily_history

-   fecha
-   valor_portfolio
-   ganancia_día
-   btc
-   usdc

## API REST

GET - /portfolio - /dashboard - /history - /prices - /statistics

POST - /buy - /sell - /deposit - /withdraw - /convert

## Indicadores

-   RSI
-   MACD
-   EMA
-   SMA
-   ATR
-   Bandas de Bollinger
-   Soportes y resistencias
-   Volumen
-   Fear & Greed
-   Dominancia BTC

## Predicción

Mostrar una recomendación explicada, sin automatizar compras o ventas: -
Tendencia. - RSI. - MACD. - Soportes y resistencias. - Probabilidad
orientativa. - Motivos de la recomendación.

## Automatización

Cada minuto: - Actualizar precios. - Recalcular portafolio. - Guardar
snapshot.

Cada día: - Resumen. - Rentabilidad. - Máximo drawdown.

## Docker

Servicios: - Frontend - Backend - PostgreSQL - Redis - Worker - Nginx

## Seguridad

-   JWT + Refresh Token
-   Argon2
-   2FA opcional
-   API Keys cifradas
-   Backups
-   Auditoría

## Mejoras futuras

-   Múltiples carteras.
-   Integración con Binance/Pionex.
-   Notificaciones.
-   Cálculo de impuestos.
-   Comparación con estrategia DCA.
-   Aplicación móvil.
-   Simulador de escenarios.
