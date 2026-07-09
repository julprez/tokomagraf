#!/usr/bin/env bash
# ============================================================
# backup.sh — Backup automático de la BD de tokomagraf
#
# Uso manual:   ./backup.sh
# Automático:   el instalador lo agrega a cron (diario)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
RETENTION_DAYS=6
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/tokomagraf_${TIMESTAMP}.sql.gz"

# ── Crear directorio de backups ───────────────────────────────
mkdir -p "${BACKUP_DIR}"

# ── Ejecutar pg_dump dentro del contenedor ───────────────────
echo "[$(date)] Iniciando backup..."

if docker compose -f "${SCRIPT_DIR}/docker-compose.prod.yml" exec -T db \
    pg_dump -U tokomagraf tokomagraf 2>/dev/null | gzip > "${BACKUP_FILE}"; then

    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] ✅ Backup creado: ${BACKUP_FILE} (${SIZE})"

    # ── Eliminar backups viejos (> 7 días) ────────────────────
    DELETED=$(find "${BACKUP_DIR}" -name "tokomagraf_*.sql.gz" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
    if [ "${DELETED}" -gt 0 ]; then
        echo "[$(date)] 🗑️  ${DELETED} backup(s) antiguo(s) eliminado(s)"
    fi

    # ── Mostrar estado ───────────────────────────────────────
    COUNT=$(find "${BACKUP_DIR}" -name "tokomagraf_*.sql.gz" | wc -l)
    TOTAL=$(du -sh "${BACKUP_DIR}" | cut -f1)
    echo "[$(date)] 📦 ${COUNT} backup(s) en ${BACKUP_DIR} (${TOTAL} total)"

else
    echo "[$(date)] ❌ Error: no se pudo crear el backup"
    exit 1
fi
