# =============================================================
# worker.py — Punto de entrada del worker Celery
# =============================================================
# Ejecutar: celery -A app.tasks.worker worker --loglevel=info
# Para beat: celery -A app.tasks.worker beat --loglevel=info

from app.tasks.celery_app import celery_app as app

__all__ = ["app"]
