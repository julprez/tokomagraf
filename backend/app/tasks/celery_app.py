# =============================================================
# celery_app.py — Configuración de Celery
# =============================================================

import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "tokomagraf",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.alert_tasks", "app.tasks.automation_tasks", "app.tasks.intelligence_tasks"],
)

# Configuración por defecto
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=5 * 60,
)

# Schedule: tareas periódicas
celery_app.conf.beat_schedule = {
    "check-alerts-every-5-minutes": {
        "task": "app.tasks.alert_tasks.check_all_alerts",
        "schedule": 300.0,  # cada 5 minutos
    },
    "update-market-every-minute": {
        "task": "app.tasks.automation_tasks.update_market_data",
        "schedule": 60.0,  # cada 1 minuto
    },
    "generate-daily-summary": {
        "task": "app.tasks.automation_tasks.generate_daily_summary",
        "schedule": 86400.0,  # cada 24 horas
    },
    "intelligence-notifications": {
        "task": "app.tasks.intelligence_tasks.generate_intelligence_notifications",
        "schedule": 21600.0,  # cada 6 horas
    },
}
