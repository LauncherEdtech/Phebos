"""Comandos do vendedor no chat — a interface do produto é o próprio WhatsApp.

Segurança (nunca enfraquecer): só números da lista `seller_numbers` podem
dar comandos. Mensagem de qualquer outro número é ignorada em silêncio.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .models import Charge, format_brl, parse_brl
from .psp.base import PspClient
from .storage import Storage

HELP_TEXT = (
    "🤖 *PixZap* — confirmação automática de Pix\n\n"
    "Comandos:\n"
    "• *cobrar 150,00 João pedido 12* — gera o Pix copia-e-cola\n"
    "• *pendentes* — cobranças aguardando pagamento\n"
    "• *hoje* — resumo do dia (pagas e total recebido)\n"
    "• *cancelar 12* — cancela a cobrança #12\n"
    "• *ajuda* — mostra esta mensagem\n\n"
    "Quando o Pix cair, eu te aviso aqui. 💸\n"
    "⚠️ Nunca entregue pedido por screenshot: espere a minha confirmação."
)

# Captura qualquer token como valor; a validação de verdade é do parse_brl,
# para que "cobrar abc" responda "valor inválido" em vez de "não entendi".
COBRAR_RE = re.compile(
    r"^cobrar\s+(?P<valor>r\$\s*\S+|\S+)(?:\s+(?P<descricao>.+))?$",
    re.IGNORECASE,
)
CANCELAR_RE = re.compile(r"^cancelar\s+#?(?P<id>\d+)$", re.IGNORECASE)


class Bot:
    def __init__(self, storage: Storage, psp: PspClient,
                 seller_numbers: list[str], tz_name: str = "America/Sao_Paulo"):
        self.storage = storage
        self.psp = psp
        self.seller_numbers = set(seller_numbers)
        self.tz = ZoneInfo(tz_name)

    def handle(self, sender: str, text: str) -> Optional[str]:
        """Processa uma mensagem e devolve a resposta (None = ignorar)."""
        if sender not in self.seller_numbers:
            return None  # regra de segurança: desconhecido não conversa com o bot

        text = text.strip()
        lowered = text.lower()

        if lowered in ("ajuda", "help", "menu", "oi", "olá", "ola"):
            return HELP_TEXT

        match = COBRAR_RE.match(text)
        if match:
            return self._create_charge(match.group("valor"),
                                       (match.group("descricao") or "").strip())

        if lowered == "pendentes":
            return self._list_pending()

        if lowered == "hoje":
            return self._daily_summary()

        match = CANCELAR_RE.match(text)
        if match:
            return self._cancel(int(match.group("id")))

        return ("Não entendi. 🤔 Mande *ajuda* para ver os comandos.")

    # ── comandos ────────────────────────────────────────────────────
    def _create_charge(self, raw_amount: str, description: str) -> str:
        amount_cents = parse_brl(raw_amount)
        if amount_cents is None:
            return ("Valor inválido. Exemplos: *cobrar 150* ou "
                    "*cobrar 89,90 Maria pedido 7*")
        pix = self.psp.create_charge(amount_cents, description)
        charge = self.storage.save_charge(Charge(
            id=None, txid=pix.txid, amount_cents=amount_cents,
            description=description, copy_paste_code=pix.copy_paste_code,
            provider=self.psp.name,
        ))
        return (
            f"✅ Cobrança {charge.summary()} criada.\n\n"
            "Encaminhe o código abaixo para o cliente pagar "
            "(Pix copia-e-cola):\n\n"
            f"{charge.copy_paste_code}\n\n"
            "Eu aviso aqui assim que o pagamento cair. 🔔"
        )

    def _list_pending(self) -> str:
        pending = self.storage.pending_charges()
        if not pending:
            return "Nenhuma cobrança pendente. 🎉"
        lines = [c.summary() for c in pending]
        total = sum(c.amount_cents for c in pending)
        return ("⏳ *Cobranças pendentes:*\n" + "\n".join(lines) +
                f"\n\nTotal a receber: {format_brl(total)}")

    def _daily_summary(self) -> str:
        now_local = datetime.now(self.tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_local.astimezone(timezone.utc).isoformat(timespec="seconds")
        paid = self.storage.paid_charges_since(start_utc)
        pending = self.storage.pending_charges()
        total = sum(c.amount_cents for c in paid)
        lines = [c.summary() for c in paid] or ["(nenhuma ainda)"]
        return (
            f"📊 *Resumo de {now_local.strftime('%d/%m/%Y')}*\n\n"
            f"Pagas hoje ({len(paid)}):\n" + "\n".join(lines) +
            f"\n\n💰 Recebido hoje: {format_brl(total)}\n"
            f"⏳ Pendentes no total: {len(pending)}"
        )

    def _cancel(self, charge_id: int) -> str:
        charge = self.storage.get_charge(charge_id)
        if charge is None:
            return f"Cobrança #{charge_id} não encontrada."
        if charge.status.value != "pendente":
            return f"Cobrança #{charge_id} está '{charge.status.value}' — não dá para cancelar."
        self.storage.mark_canceled(charge_id)
        return f"🚫 Cobrança {charge.summary()} cancelada."

    # ── notificações da conciliação ─────────────────────────────────
    def notify_sellers(self, wa_client, message: str) -> None:
        for number in self.seller_numbers:
            wa_client.send_text(number, message)
