#!/usr/bin/env bash
# ============================================================
# install-remote.sh — Instalador remoto de tokomagraf
#
# Uso (desde cualquier VPS limpio):
#   curl -sSL https://raw.githubusercontent.com/TU-USUARIO/tokomagraf/main/install-remote.sh | bash
#
# O si tenés tu propio dominio:
#   curl -sSL https://tokomagraf.com/install.sh | bash
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║       tokomagraf — Instalador       ║"
echo "  ║    Gestor de Cartera Cripto BTC     ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── 0. Verificar requisitos mínimos ───────────────────────────
echo -e "${YELLOW}[0]${NC} Verificando sistema..."
if ! command -v curl &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq curl
fi
if ! command -v git &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq git
fi

# ── 1. Clonar el repositorio ─────────────────────────────────
# ── CAMBIAR POR TU REPO ──────────────────────────────────
REPO_URL="https://github.com/TU-USUARIO/tokomagraf.git"
# ─────────────────────────────────────────────────────────
echo -e "${YELLOW}[1]${NC} Clonando tokomagraf..."
if [ -d "tokomagraf" ]; then
    echo "  La carpeta tokomagraf ya existe, actualizando..."
    cd tokomagraf && git pull
else
    git clone "$REPO_URL" tokomagraf
    cd tokomagraf
fi

# ── 2. Ejecutar el instalador principal ───────────────────────
echo -e "${YELLOW}[2]${NC} Ejecutando instalador..."
chmod +x install.sh
exec ./install.sh
