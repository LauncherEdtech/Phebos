"""Gestão de chaves pelo dashboard: salvar com segurança e testar conexões.

As chaves ficam em DATA_DIR/secrets.env (volume compartilhado entre os
containers), com permissão 600. Elas SOBRESCREVEM as do .env — assim o que
você salva no dashboard vale na hora, e o agente recarrega no próximo ciclo.
Nenhum endpoint devolve a chave completa: só uma prévia mascarada.
"""

import logging
import os
from pathlib import Path

import requests

from . import config

log = logging.getLogger("phebos")

KEY_FIELDS = [
    "GEMINI_API_KEY",
    "BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET",
    "ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def read_secrets(path: Path | None = None) -> dict:
    path = path or config.SECRETS_FILE
    secrets: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                secrets[key.strip()] = value.strip()
    return secrets


def effective_value(field: str) -> str:
    """Valor em vigor: secrets.env (dashboard) tem prioridade sobre o ambiente."""
    return read_secrets().get(field) or os.environ.get(field, "")


def save_secrets(updates: dict, path: Path | None = None) -> list[str]:
    """Mescla os campos não vazios no secrets.env. Retorna os campos salvos."""
    path = path or config.SECRETS_FILE
    current = read_secrets(path)
    saved = []
    for field in KEY_FIELDS:
        value = (updates.get(field) or "").strip()
        if value:
            current[field] = value
            saved.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{k}={v}" for k, v in current.items()) + "\n")
    path.chmod(0o600)
    return saved


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[0] + "…" + value[-1]
    return value[:4] + "…" + value[-4:]


def masked_status() -> dict:
    return {
        field: {"set": bool(effective_value(field)), "preview": _mask(effective_value(field))}
        for field in KEY_FIELDS
    }


# ── testes de conexão (1 chamada barata por serviço) ─────────────────
def test_gemini() -> dict:
    key = effective_value("GEMINI_API_KEY")
    if not key:
        return {"ok": None, "detail": "chave não configurada"}
    try:
        from google import genai
        client = genai.Client(api_key=key)
        models = client.models.list()
        next(iter(models), None)
        return {"ok": True, "detail": "autenticado na API do Gemini"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}


def test_binance() -> dict:
    key = effective_value("BINANCE_TESTNET_API_KEY")
    secret = effective_value("BINANCE_TESTNET_API_SECRET")
    if not key or not secret:
        return {"ok": None, "detail": "chaves não configuradas"}
    try:
        from .brokers.binance import BinanceBroker
        broker = BinanceBroker(key, secret, live=False)
        account = broker._signed("GET", "/api/v3/account")
        balances = sum(1 for b in account.get("balances", [])
                       if float(b["free"]) + float(b["locked"]) > 0)
        return {"ok": True, "detail": f"conta da testnet OK ({balances} ativos com saldo)"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}


def test_alpaca() -> dict:
    key = effective_value("ALPACA_PAPER_API_KEY")
    secret = effective_value("ALPACA_PAPER_API_SECRET")
    if not key or not secret:
        return {"ok": None, "detail": "chaves não configuradas"}
    try:
        from .brokers.alpaca import AlpacaBroker
        broker = AlpacaBroker(key, secret, live=False)
        account = broker._get(broker.base_url, "/v2/account")
        return {"ok": True, "detail": f"conta paper OK (status: {account.get('status', '?')})"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}


def test_telegram() -> dict:
    token = effective_value("TELEGRAM_BOT_TOKEN")
    chat_id = effective_value("TELEGRAM_CHAT_ID")
    if not token:
        return {"ok": None, "detail": "token não configurado"}
    try:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10).json()
        if not me.get("ok"):
            return {"ok": False, "detail": f"token inválido: {me.get('description', '?')}"}
        bot_name = me["result"].get("username", "?")
        if not chat_id:
            return {"ok": False, "detail": f"bot @{bot_name} OK, mas falta o TELEGRAM_CHAT_ID"}
        sent = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ Teste do Phebos: conexão funcionando!"},
            timeout=10,
        ).json()
        if sent.get("ok"):
            return {"ok": True, "detail": f"mensagem de teste enviada por @{bot_name} — confira o Telegram"}
        return {"ok": False, "detail": f"chat_id inválido: {sent.get('description', '?')}"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}


def run_tests() -> dict:
    return {
        "gemini": test_gemini(),
        "binance": test_binance(),
        "alpaca": test_alpaca(),
        "telegram": test_telegram(),
    }
