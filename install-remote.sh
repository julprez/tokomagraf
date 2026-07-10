#!/usr/bin/env bash
# ============================================================
# install-remote.sh — Instalador remoto de tokomagraf
#
# Uso (desde cualquier VPS limpio):
#   curl -sSL https://raw.githubusercontent.com/julprez/tokomagraf/main/install-remote.sh | bash
#
# O si tenés tu propio dominio:
#   curl -sSL https://tokomagraf.com/install.sh | bash
# ============================================================
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║       tokomagraf — Instalador       ║"
echo "  ║    Gestor de Cartera Cripto BTC     ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── 0. Configurar DNS del sistema (VPS con IPv6 roto) ─────────
echo -e "${YELLOW}[0]${NC} Verificando conectividad..."
# Some VPS providers have broken IPv6 DNS — fix system DNS first
if ! getent hosts github.com >/dev/null 2>&1; then
    echo "  DNS no funciona — configurando Google/Cloudflare DNS..."
    # Try systemd-resolved first
    if systemctl is-active systemd-resolved >/dev/null 2>&1; then
        mkdir -p /etc/systemd/resolved.conf.d
        cat > /etc/systemd/resolved.conf.d/99-tokomagraf-dns.conf << 'EOF'
[Resolve]
DNS=8.8.8.8 1.1.1.1
FallbackDNS=8.8.4.4
DNSOverTLS=no
DNSSEC=no
EOF
        systemctl daemon-reload 2>/dev/null || true
        systemctl restart systemd-resolved 2>/dev/null || true
        sleep 2
    fi
    # Also fix /etc/resolv.conf directly as fallback
    if ! getent hosts github.com >/dev/null 2>&1; then
        rm -f /etc/resolv.conf
        echo "nameserver 8.8.8.8" > /etc/resolv.conf
        echo "nameserver 1.1.1.1" >> /etc/resolv.conf
        echo "nameserver 8.8.4.4" >> /etc/resolv.conf
        sleep 1
    fi
    if getent hosts github.com >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} DNS arreglado — conectividad restaurada"
    else
        echo -e "  ${YELLOW}⚠${NC} No se pudo arreglar DNS. Intentando igual..."
    fi
else
    echo -e "  ${GREEN}✓${NC} DNS funciona correctamente"
fi

# ── 1. Verificar requisitos mínimos ───────────────────────────
echo -e "${YELLOW}[1]${NC} Verificando sistema..."
if ! command -v curl &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq curl
fi
if ! command -v git &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq git
fi

# ── 2. Clonar el repositorio ─────────────────────────────────
# ── CAMBIAR POR TU REPO ──────────────────────────────────
REPO_URL="https://github.com/julprez/tokomagraf.git"
# ─────────────────────────────────────────────────────────
echo -e "${YELLOW}[2]${NC} Clonando tokomagraf..."
if [ -d "tokomagraf" ]; then
    echo "  La carpeta tokomagraf ya existe, actualizando..."
    cd tokomagraf && git pull
else
    echo "  Clonando repositorio..."
    if ! git clone "$REPO_URL" tokomagraf; then
        echo -e "  ${RED}ERROR${NC}: No se pudo clonar el repositorio."
        echo "    Verificá que la URL sea correcta y que el VPS tenga acceso a GitHub."
        echo "    URL: $REPO_URL"
        exit 1
    fi
    cd tokomagraf
fi

# ── 3. Ejecutar el instalador principal ───────────────────────
echo -e "${YELLOW}[3]${NC} Ejecutando instalador..."
chmod +x install.sh
exec ./install.sh
