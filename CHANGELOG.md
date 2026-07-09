# Changelog

## v1.0.0 — Lanzamiento inicial (2026-07-09)

### 🎨 Diseño y UX
- Dashboard con toggle Portfolio/BTC, zonas de ganancia/pérdida coloreadas y ranking de volatilidad
- Diseño dark mode con tarjetas, gradientes y micro-interacciones
- **Responsive mobile-first**: menú hamburguesa, sidebar deslizante, gráficos y tablas adaptables
- **Toast notifications**: sistema de notificaciones con auto-dismiss, 4 tipos y animación
- **Skeleton loaders**: 5 variantes (Card, Chart, Table, Dashboard, Skeleton base)
- **Empty states**: componente reutilizable con icono, título, descripción y acción
- **Page transitions**: fade-in al navegar entre páginas
- **Breadcrumbs**: navegación jerárquica en todas las páginas
- Personalización de opacidad de zonas ganancia/pérdida desde Configuración

### 📊 Dashboard
- Patrimonio total en USD con P&L diario y mensual
- Gráfico de evolución 7 días con toggle Portfolio/BTC
- Línea de referencia de capital aportado
- Zonas de ganancia (verde) y pérdida (roja) con etiquetas
- Ranking de volatilidad diaria del portfolio (top 4)
- Tarjeta de resultado diario con sparkline intradía y countdown de cierre
- Indicadores: RSI, tendencia, soporte/resistencia

### 💱 Operaciones
- Formulario para comprar, vender, depositar y retirar BTC/USDC/EUR
- Cálculo automático de totales, precio BTC actual y conversión USDC↔BTC
- Botones rápidos de porcentaje (Max, 50%, 25%) para ventas/retiros
- Comisión configurable (monto fijo o porcentaje)
- **Notas de trading**: campo de texto para registrar el razonamiento de cada operación
- Integración con el Simulador: precarga automática del formulario

### 📈 Historial y Análisis
- 7 gráficos interactivos: evolución patrimonio, BTC 90d, P&L diario, P&L acumulado, aportes, coste medio, rentabilidad mensual
- Análisis técnico: RSI, MACD, SMA 50/200, Golden/Death Cross
- Lista de operaciones con diseño responsive
- **Export CSV**: descarga de todas las operaciones en formato CSV

### 🧠 Predicción de Mercado
- Score de predicción 0-100% con anillo visual animado
- 8 indicadores combinados: RSI, MACD, SMA, soporte/resistencia, Fear & Greed, dominancia BTC, volumen, upside/downside
- Motivos detallados del análisis con pesos e impacto
- Señal de compra/venta/neutral con colores

### 📊 DCA (Dollar Cost Averaging)
- Comparativa completa: tu estrategia vs DCA automático
- Tabla con 9 indicadores (capital, BTC, valor, beneficio, rentabilidad, coste medio, drawdown)
- 3 gráficos: evolución comparada, diferencia acumulada, BTC acumulados
- **Insights de IA**: observaciones, puntaje de timing, métricas de compras/ventas
- Configuración de frecuencia DCA (semanal/mensual)

### 🎯 Simulador de Escenarios
- Proyección del portfolio a distintos precios de BTC (-30%, Actual, +50%, 2x, 3x, personalizado)
- Datos cargados automáticamente desde la cartera real
- **Gráfico de barras** comparativo de todos los escenarios
- **Sugerencias de acción**: cuánto comprar/vender hoy para cada escenario
- **Botón Aplicar**: navega directo a Operaciones con el formulario precargado

### 🔔 Alertas
- Creación de alertas: precio supera, precio baja de, profit target %, stop loss %
- Badge de notificaciones no leídas en el menú lateral
- Indicador de distancia al objetivo en % y precio actual
- Toggle activar/desactivar y eliminar

### 💰 Vista Fiscal
- P&L realizado por año con cálculo FIFO simplificado
- Separación correcta de compras/ventas vs depósitos/retiros
- Disclaimer de no-asesoramiento fiscal

### 🔒 Seguridad
- **Rate limiting**: 200 req/min global en la API (slowapi)
- **Security headers**: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **CORS**: configurable por dominio, soporte HTTP/HTTPS automático
- Autenticación: JWT + seed phrase de 6 palabras + email/password
- Nginx cache optimizado (1h en producción)

### 🐳 Infraestructura y DevOps
- **Docker Compose**: 6 servicios (DB, Redis, Backend, Worker, Frontend, Caddy)
- **Caddy SSL**: HTTPS automático con Let's Encrypt, zero-config
- **Healthchecks**: en todos los servicios con autoreinicio
- **Backup automático**: pg_dump diario con 7 días de retención
- **Instalador automático**: un solo comando (`curl | bash`)
- **Docker Compose separado**: desarrollo (hot-reload) y producción (SSL)
- Rate limiting, healthchecks, y seguridad en nginx

### 🛠️ Stack técnico
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts, React Query, React Router
- **Backend**: FastAPI, SQLAlchemy, Celery, slowapi, pandas
- **Base de datos**: PostgreSQL 16, Redis 7
- **Proxy**: Caddy 2 (SSL), Nginx (static files)

---

## 📦 Archivos

| Archivo | Propósito |
|---|---|
| `docker-compose.yml` | Desarrollo |
| `docker-compose.prod.yml` | Producción (Caddy + SSL) |
| `docker-compose.dev.yml` | Desarrollo (hot-reload) |
| `Caddyfile` | Configuración SSL automática |
| `install.sh` | Instalador interactivo |
| `install-remote.sh` | Instalador remoto (`curl \| bash`) |
| `backup.sh` | Backup diario PostgreSQL (7 días) |
| `nginx.conf` | Configuración Nginx (SPA + API proxy) |
| `.env.example` | Template de variables de entorno |
