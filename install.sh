#!/usr/bin/env bash
# ============================================================
# install.sh — Instalador de tokomagraf en un VPS
#
# Uso:
#   chmod +x install.sh
#   ./install.sh
#
# O en una línea:
#   curl -sSL https://tu-servidor/install.sh | bash
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

# ── 1. Verificar Docker ──────────────────────────────────────
echo -e "${YELLOW}[1/8]${NC} Verificando Docker..."
if ! command -v docker &>/dev/null; then
    echo "  Instalando Docker..."
    curl -fsSL https://get.docker.com | bash
fi
if ! docker compose version &>/dev/null 2>&1; then
    echo "  Instalando Docker Compose..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
fi
echo -e "  ${GREEN}✓${NC} Docker listo"

# ── 1b. Configurar DNS de Docker (evita errores IPv6 en VPS) ─
echo -e "${YELLOW}[2/8]${NC} Configurando DNS de Docker..."
DOCKER_DAEMON="/etc/docker/daemon.json"
mkdir -p /etc/docker
if [ ! -f "$DOCKER_DAEMON" ] || ! grep -q '"dns"' "$DOCKER_DAEMON" 2>/dev/null; then
    # Backup if existing
    [ -f "$DOCKER_DAEMON" ] && cp "$DOCKER_DAEMON" "${DOCKER_DAEMON}.bak.$(date +%s)"
    cat > "$DOCKER_DAEMON" << 'DAEMONEOF'
{
  "dns": ["8.8.8.8", "1.1.1.1"],
  "ipv6": false
}
DAEMONEOF
    systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || true
    # Wait for Docker to be ready
    for i in $(seq 1 15); do
        if docker info >/dev/null 2>&1; then break; fi
        sleep 1
    done
    echo -e "  ${GREEN}✓${NC} Docker configurado con DNS 8.8.8.8 / 1.1.1.1 (IPv6 deshabilitado)"
else
    echo -e "  ${GREEN}✓${NC} DNS de Docker ya configurado"
fi

# ── 3. Configurar variables de entorno ────────────────────────
echo -e "${YELLOW}[3/8]${NC} Configurando entorno..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
    fi
    # Generar secretos automáticos
    DB_PASS=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)
    sed -i "s/cambiame-por-una-contrasena-segura/${DB_PASS}/" .env
    sed -i "s/cambiame-por-un-secreto-largo-y-aleatorio/${JWT_SECRET}/" .env
    echo -e "  ${GREEN}✓${NC} Archivo .env creado con secretos aleatorios"
else
    echo -e "  ${GREEN}✓${NC} Archivo .env ya existe"
fi

# ── 4. Preguntar dominio ─────────────────────────────────────
echo -e "${YELLOW}[4/8]${NC} Configuración de dominio"
echo ""
echo "  Si tenés un dominio, Caddy obtiene SSL automático (HTTPS)."
echo "  Si no, se usa HTTP simple con la IP del servidor."
echo ""
read -p "  ¿Tenés un dominio? (dejá vacío para usar solo IP): " DOMAIN < /dev/tty
if [ -n "$DOMAIN" ]; then
    # Ensure domain doesn't have http:// prefix
    DOMAIN=$(echo "$DOMAIN" | sed 's|^https\?://||' | sed 's|/.*||')
    sed -i "s/^DOMAIN=.*/DOMAIN=${DOMAIN}/" .env
    echo -e "  ${GREEN}✓${NC} Dominio configurado: ${DOMAIN}"
    echo -e "     Asegurate de que ${CYAN}${DOMAIN}${NC} apunte a la IP de este servidor"
else
    sed -i "s/^DOMAIN=.*/DOMAIN=/" .env
    echo -e "  ${GREEN}✓${NC} Se usará solo HTTP con la IP del servidor"
fi

# ── 5. Abrir puertos en firewall ──────────────────────────────
echo -e "${YELLOW}[5/8]${NC} Configurando firewall..."
if command -v ufw &>/dev/null; then
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Puertos 80 (HTTP) y 443 (HTTPS) abiertos"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --add-port=80/tcp --permanent 2>/dev/null || true
    firewall-cmd --add-port=443/tcp --permanent 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Puertos 80 y 443 abiertos"
else
    echo -e "  ${YELLOW}⚠${NC} No se detectó firewall. Asegurate de abrir puertos 80 y 443 manualmente"
fi

# ── 6. Construir e iniciar ────────────────────────────────────
echo -e "${YELLOW}[6/8]${NC} Construyendo e iniciando tokomagraf..."
echo "  Esto puede tardar unos minutos la primera vez..."
docker compose -f docker-compose.prod.yml up -d --build 2>&1 | tail -5

# ── 7. Configurar backup automático ───────────────────────────
echo -e "${YELLOW}[7/8]${NC} Configurando backup automático (diario, 7 días de retención)..."
chmod +x backup.sh
# Agregar a cron si no existe
CRON_JOB="0 3 * * * cd $(pwd) && bash backup.sh >> backups/backup.log 2>&1"
if crontab -l 2>/dev/null | grep -qF "backup.sh"; then
    echo -e "  ${GREEN}✓${NC} Backup ya estaba configurado en cron"
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo -e "  ${GREEN}✓${NC} Backup programado todos los días a las 3 AM"
fi
mkdir -p backups
echo -e "  ${GREEN}✓${NC} Backups se guardan en ./backups/ (7 días de retención)"

# ── 8. Esperar a que Caddy obtenga SSL ────────────────────────
echo -e "${YELLOW}[8/8]${NC} Esperando que los servicios estén listos..."
sleep 5

# ── Mostrar info de acceso ────────────────────────────────────
IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      ¡tokomagraf instalado con éxito!      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
if [ -n "$DOMAIN" ]; then
    echo -e "  🌐 URL: ${CYAN}https://${DOMAIN}${NC}"
    echo -e "     (HTTP redirige automáticamente a HTTPS)"
    echo -e "     SSL gestionado por Let's Encrypt — se renueva solo"
else
    echo -e "  🌐 URL: ${CYAN}http://${IP}${NC}"
fi
echo ""
echo -e "  📝 Comandos útiles:"
echo -e "     docker compose -f docker-compose.prod.yml logs -f    # Ver logs"
echo -e "     docker compose -f docker-compose.prod.yml logs caddy # Logs de SSL"
echo -e "     docker compose -f docker-compose.prod.yml restart    # Reiniciar"
echo -e "     docker compose -f docker-compose.prod.yml down       # Detener"
echo -e "     bash backup.sh                                      # Backup manual"
echo ""
