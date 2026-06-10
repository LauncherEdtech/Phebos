"""Notificações via Telegram (opcionais — ativam só se as credenciais existirem).

Crie um bot com o @BotFather, pegue o token, mande uma mensagem para o bot e
descubra seu chat_id em https://api.telegram.org/bot<TOKEN>/getUpdates
"""

import logging
import os

import requests

log = logging.getLogger("phebos")


class Notifier:
    def __init__(self, enabled: bool = True):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = enabled and bool(self.token and self.chat_id)
        if enabled and not self.enabled:
            log.info("Telegram desativado (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes no .env)")

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            ).raise_for_status()
        except Exception as exc:  # notificação nunca pode derrubar o ciclo
            log.warning("falha ao enviar notificação Telegram: %s", exc)

    # ── mensagens prontas ───────────────────────────────────────────
    def startup(self, mode: str, markets: list[str], interval_minutes: int) -> None:
        banner = "🔴 DINHEIRO REAL" if mode == "live" else "🟦 DEMO (fictício)"
        self.send(
            f"🤖 <b>Phebos iniciado</b>\n"
            f"Modo: {banner}\n"
            f"Mercados: {', '.join(markets)}\n"
            f"Intervalo: {interval_minutes} min"
        )

    def trade(self, mode: str, market: str, side: str, symbol: str,
              notional_usd: float, rationale: str, order_id: str) -> None:
        emoji = "🟢 COMPRA" if side == "buy" else "🔴 VENDA"
        tag = "REAL" if mode == "live" else "demo"
        self.send(
            f"{emoji} <b>{symbol}</b> — ${notional_usd:.2f} <i>({tag} · {market})</i>\n"
            f"💡 {rationale}\n"
            f"🧾 ordem: {order_id}"
        )

    def vetoed(self, market: str, side: str, symbol: str,
               notional_usd: float, reason: str) -> None:
        self.send(
            f"🚫 Ordem vetada pelo risco: {side} <b>{symbol}</b> ${notional_usd:.2f} "
            f"<i>({market})</i>\n⚠️ {reason}"
        )

    def error(self, market: str, message: str) -> None:
        self.send(f"❗ <b>Erro no ciclo</b> ({market}):\n<code>{message[:500]}</code>")
