# ============================================================
# Dockerfile — tokomagraf BTC Price Bot
# ============================================================

FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para Chromium (Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libwayland-client0 libwayland-egl1 \
    ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Chromium de Playwright
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# Copiar aplicación
COPY *.py ./
COPY card_templates/ card_templates/

# Health check simple
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os; exit(0) if os.path.exists('/app/main.py') else exit(1)"

CMD ["python", "main.py"]
