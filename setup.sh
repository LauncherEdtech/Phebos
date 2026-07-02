#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  PixZap — Instalador automático                                  ║
# ║  Instala Docker, clona o repositório, configura as chaves e      ║
# ║  sobe o serviço. Pode ser executado mais de uma vez.             ║
# ║                                                                  ║
# ║  Uso:  curl -fsSL https://raw.githubusercontent.com/LauncherEdtech/Phebos/main/setup.sh | bash
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

REPO_URL="https://github.com/LauncherEdtech/Phebos.git"
INSTALL_DIR="${PIXZAP_DIR:-$HOME/PixZap}"

# cores
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[1;34m'; N='\033[0m'
say()  { echo -e "${B}▸${N} $*"; }
ok()   { echo -e "${G}✔${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
die()  { echo -e "${R}✘ $*${N}" >&2; exit 1; }

# lê do terminal mesmo quando o script vem via "curl | bash"
ask() { # ask "pergunta" VAR [secreto]
  local prompt="$1" var="$2" secret="${3:-}"
  local value=""
  if [ -n "$secret" ]; then
    read -r -s -p "$(echo -e "${B}?${N} $prompt: ")" value < /dev/tty; echo
  else
    read -r -p "$(echo -e "${B}?${N} $prompt: ")" value < /dev/tty
  fi
  printf -v "$var" '%s' "$value"
}

echo
echo -e "${B}╔════════════════════════════════════════╗${N}"
echo -e "${B}║   💸 PixZap — Instalador automático     ║${N}"
echo -e "${B}╚════════════════════════════════════════╝${N}"
echo

# ── 1. pré-requisitos ────────────────────────────────────────────────
[ "$(uname -s)" = "Linux" ] || die "Este instalador é para Linux (Ubuntu/Debian). No Windows, use WSL2."

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null || die "Rode como root ou instale o sudo."
  SUDO="sudo"
fi

command -v curl >/dev/null || { say "Instalando curl..."; $SUDO apt-get update -qq && $SUDO apt-get install -y -qq curl; }
command -v git  >/dev/null || { say "Instalando git...";  $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git; }

# ── 2. Docker ────────────────────────────────────────────────────────
if command -v docker >/dev/null 2>&1; then
  ok "Docker já instalado ($(docker --version | cut -d',' -f1))"
else
  say "Instalando Docker (script oficial)..."
  curl -fsSL https://get.docker.com | $SUDO sh
  ok "Docker instalado"
fi

if [ -n "$SUDO" ] && ! id -nG "$USER" | grep -qw docker; then
  $SUDO usermod -aG docker "$USER" || true
  warn "Seu usuário foi adicionado ao grupo docker (vale a partir do próximo login)."
fi

docker compose version >/dev/null 2>&1 || DOCKER_COMPOSE_MISSING=1
if [ "${DOCKER_COMPOSE_MISSING:-0}" = "1" ]; then
  say "Instalando o plugin docker compose..."
  $SUDO apt-get update -qq && $SUDO apt-get install -y -qq docker-compose-plugin
fi
ok "Docker Compose disponível"

# ── 3. código ────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  say "Repositório já existe em $INSTALL_DIR — atualizando..."
  git -C "$INSTALL_DIR" pull --ff-only || warn "Não foi possível atualizar (alterações locais?); seguindo com a versão atual."
else
  say "Clonando o PixZap em $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ── 4. chaves ────────────────────────────────────────────────────────
if [ -f .env ]; then
  ok "Arquivo .env já existe — mantendo as chaves atuais."
else
  say "Configuração das chaves (deixe em branco para preencher depois no .env):"
  ask "WHATSAPP_ACCESS_TOKEN (Meta → WhatsApp → API Setup)" WA_TOKEN secreto
  ask "WHATSAPP_VERIFY_TOKEN (invente um segredo para o webhook)" WA_VERIFY
  ask "ASAAS_API_KEY (sandbox: https://sandbox.asaas.com)" ASAAS_KEY secreto
  ask "ASAAS_WEBHOOK_TOKEN (o mesmo valor configurado no painel do Asaas)" ASAAS_WH
  cat > .env <<EOF
WHATSAPP_ACCESS_TOKEN=${WA_TOKEN}
WHATSAPP_VERIFY_TOKEN=${WA_VERIFY}
ASAAS_API_KEY=${ASAAS_KEY}
ASAAS_WEBHOOK_TOKEN=${ASAAS_WH}
MP_ACCESS_TOKEN=
MP_WEBHOOK_SECRET=
EOF
  ok "Arquivo .env criado."
fi

if ! grep -q '^seller_numbers: \[\]' config.yaml 2>/dev/null; then
  ok "config.yaml já personalizado — mantendo."
else
  ask "Seu número de WhatsApp (formato 5511999998888)" SELLER
  if [ -n "$SELLER" ]; then
    sed -i "s/^seller_numbers: \[\]/seller_numbers: [\"$SELLER\"]/" config.yaml
    ok "Número autorizado: $SELLER"
  else
    warn "Nenhum número configurado — edite seller_numbers no config.yaml."
  fi
fi

# ── 5. sobe ──────────────────────────────────────────────────────────
say "Subindo o PixZap..."
$SUDO docker compose up -d --build
echo
ok "PixZap no ar! Health check: http://localhost:8000/health"
echo -e "  ${B}Próximos passos:${N}"
echo "  1. Aponte um domínio com HTTPS para esta máquina (Meta e PSPs exigem)."
echo "  2. Configure o webhook do WhatsApp:  https://SEU_DOMINIO/webhook/whatsapp"
echo "  3. Configure o webhook do PSP:       https://SEU_DOMINIO/webhook/psp"
echo "  4. Manual completo: GUIA.md"
