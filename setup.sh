#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Phebos — Instalador automático                                  ║
# ║  Instala Docker, clona o repositório, configura as chaves e      ║
# ║  sobe o agente + dashboard. Pode ser executado mais de uma vez.  ║
# ║                                                                  ║
# ║  Uso:  curl -fsSL https://raw.githubusercontent.com/LauncherEdtech/Phebos/main/setup.sh | bash
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

REPO_URL="https://github.com/LauncherEdtech/Phebos.git"
INSTALL_DIR="${PHEBOS_DIR:-$HOME/Phebos}"

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
echo -e "${B}║   ✦ Phebos — Instalador automático     ║${N}"
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
  say "Clonando o Phebos em $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Código pronto"

# ── 4. chaves (.env) ─────────────────────────────────────────────────
if [ -f .env ]; then
  echo
  warn "Já existe um arquivo .env configurado."
  ask "Quer reconfigurar as chaves? (s/N)" RECONF
  case "${RECONF,,}" in
    s|sim|y|yes) CONFIGURE_ENV=1 ;;
    *) CONFIGURE_ENV=0; ok "Mantendo o .env atual" ;;
  esac
else
  CONFIGURE_ENV=1
fi

CRYPTO_ON=1; STOCKS_ON=1
if [ "$CONFIGURE_ENV" = "1" ]; then
  echo
  echo -e "${B}── Configuração das chaves (modo DEMO: tudo gratuito) ──${N}"
  echo "  Deixe em branco o que não tiver — o mercado correspondente será desativado."
  echo

  echo "1/4 · Gemini (obrigatória) — crie grátis em https://aistudio.google.com/apikey"
  ask "GEMINI_API_KEY" GEMINI_KEY secreto
  [ -n "$GEMINI_KEY" ] || die "A chave do Gemini é obrigatória — é o cérebro do agente."

  echo
  echo "2/4 · Binance TESTNET (cripto, dinheiro fictício) — https://testnet.binance.vision"
  ask "BINANCE_TESTNET_API_KEY (Enter para pular)" BIN_KEY
  BIN_SECRET=""
  if [ -n "$BIN_KEY" ]; then ask "BINANCE_TESTNET_API_SECRET" BIN_SECRET secreto; else CRYPTO_ON=0; fi

  echo
  echo "3/4 · Alpaca PAPER (ações EUA, dinheiro fictício) — https://alpaca.markets"
  ask "ALPACA_PAPER_API_KEY (Enter para pular)" ALP_KEY
  ALP_SECRET=""
  if [ -n "$ALP_KEY" ]; then ask "ALPACA_PAPER_API_SECRET" ALP_SECRET secreto; else STOCKS_ON=0; fi

  [ "$CRYPTO_ON" = "1" ] || [ "$STOCKS_ON" = "1" ] || die "Configure ao menos um mercado (Binance testnet ou Alpaca paper)."

  echo
  echo "4/4 · Telegram (opcional — avisos de trades no celular)"
  ask "TELEGRAM_BOT_TOKEN (Enter para pular)" TG_TOKEN
  TG_CHAT=""
  [ -n "$TG_TOKEN" ] && ask "TELEGRAM_CHAT_ID" TG_CHAT

  cat > .env <<ENV
GEMINI_API_KEY=$GEMINI_KEY
TELEGRAM_BOT_TOKEN=$TG_TOKEN
TELEGRAM_CHAT_ID=$TG_CHAT
BINANCE_TESTNET_API_KEY=$BIN_KEY
BINANCE_TESTNET_API_SECRET=$BIN_SECRET
BINANCE_LIVE_API_KEY=
BINANCE_LIVE_API_SECRET=
ALPACA_PAPER_API_KEY=$ALP_KEY
ALPACA_PAPER_API_SECRET=$ALP_SECRET
ALPACA_LIVE_API_KEY=
ALPACA_LIVE_API_SECRET=
PHEBOS_CONFIRM_LIVE=
ENV
  chmod 600 .env
  ok "Arquivo .env criado (permissão restrita ao seu usuário)"

  # desativa no config.yaml os mercados sem chave
  if [ "$CRYPTO_ON" = "0" ]; then
    python3 - <<'PY' 2>/dev/null || sed -i '/^  crypto:/,/^  [a-z]/ s/enabled: true/enabled: false/' config.yaml
import re, pathlib
p = pathlib.Path("config.yaml"); t = p.read_text()
t = re.sub(r"(crypto:\n\s*enabled:) true", r"\1 false", t)
p.write_text(t)
PY
    warn "Mercado cripto desativado (sem chaves da Binance)."
  fi
  if [ "$STOCKS_ON" = "0" ]; then
    python3 - <<'PY' 2>/dev/null || sed -i '/^  stocks:/,/^[a-z]/ s/enabled: true/enabled: false/' config.yaml
import re, pathlib
p = pathlib.Path("config.yaml"); t = p.read_text()
t = re.sub(r"(stocks:\n\s*enabled:) true", r"\1 false", t)
p.write_text(t)
PY
    warn "Mercado de ações desativado (sem chaves da Alpaca)."
  fi
fi

# ── 5. subir os serviços ─────────────────────────────────────────────
echo
say "Construindo e subindo os containers (pode levar alguns minutos na 1ª vez)..."
$SUDO docker compose up -d --build

echo
say "Status dos serviços:"
$SUDO docker compose ps

echo
echo -e "${G}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${G}║                 ✦ Phebos instalado! ✦                    ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════════════╝${N}"
echo
echo -e "  📊 Dashboard:        ${B}http://localhost:8000${N}"
echo -e "     (de outro PC:     ssh -L 8000:localhost:8000 $USER@IP-desta-máquina)"
echo
echo -e "  Comandos úteis (dentro de $INSTALL_DIR):"
echo -e "    ${B}$SUDO docker compose logs -f agent${N}     → acompanhar o agente"
echo -e "    ${B}$SUDO docker compose exec agent python -m phebos.main evaluate${N} → relatório demo"
echo -e "    ${B}$SUDO docker compose exec agent touch /app/data/KILL${N}  → KILL SWITCH"
echo -e "    ${B}$SUDO docker compose restart${N}           → aplicar mudanças do config.yaml"
echo
echo -e "  📖 Manual completo: GUIA.md no repositório"
echo -e "  ${Y}Modo DEMO ativo — dinheiro fictício. Sem risco.${N}"
echo
