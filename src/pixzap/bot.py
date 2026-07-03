"""Comandos do vendedor no chat — a interface do produto é o próprio WhatsApp.

Segurança (nunca enfraquecer): só números da lista `seller_numbers` podem
dar comandos. Mensagem de qualquer outro número é ignorada em silêncio.

Os comandos são os mesmos em todos os idiomas (cobrar/pendentes/hoje/...);
o que muda com o `language` do config são as RESPOSTAS (ver i18n.py).
"""

import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .auth import make_token
from .i18n import DEFAULT_LANG, status_label, t
from .models import Charge, format_brl, parse_brl
from .psp.base import PspClient
from .storage import Storage

# Captura qualquer token como valor; a validação de verdade é do parse_brl,
# para que "cobrar abc" responda "valor inválido" em vez de "não entendi".
COBRAR_RE = re.compile(
    r"^cobrar\s+(?P<valor>r\$\s*\S+|\S+)(?:\s+(?P<descricao>.+))?$",
    re.IGNORECASE,
)
CANCELAR_RE = re.compile(r"^cancelar\s+#?(?P<id>\d+)$", re.IGNORECASE)


class Bot:
    def __init__(self, storage: Storage, psp: PspClient,
                 seller_numbers: list[str], tz_name: str = "America/Sao_Paulo",
                 lang: str = DEFAULT_LANG, public_url: str = "",
                 dashboard_secret: str = ""):
        self.storage = storage
        self.psp = psp
        self.seller_numbers = set(seller_numbers)
        self.tz = ZoneInfo(tz_name)
        self.lang = lang
        self.public_url = public_url.rstrip("/")
        self.dashboard_secret = dashboard_secret

    def handle(self, sender: str, text: str) -> Optional[str]:
        """Processa uma mensagem e devolve a resposta (None = ignorar)."""
        if sender not in self.seller_numbers:
            return None  # regra de segurança: desconhecido não conversa com o bot

        text = text.strip()
        lowered = text.lower()

        if lowered in ("ajuda", "help", "menu", "oi", "olá", "ola", "hola", "hi"):
            return t(self.lang, "help")

        match = COBRAR_RE.match(text)
        if match:
            return self._create_charge(match.group("valor"),
                                       (match.group("descricao") or "").strip())

        if lowered == "pendentes":
            return self._list_pending()

        if lowered == "hoje":
            return self._daily_summary()

        if lowered in ("painel", "panel", "dashboard"):
            return self._panel_link(sender)

        match = CANCELAR_RE.match(text)
        if match:
            return self._cancel(int(match.group("id")))

        return t(self.lang, "unknown_command")

    # ── comandos ────────────────────────────────────────────────────
    def _create_charge(self, raw_amount: str, description: str) -> str:
        amount_cents = parse_brl(raw_amount)
        if amount_cents is None:
            return t(self.lang, "invalid_amount")
        pix = self.psp.create_charge(amount_cents, description)
        charge = self.storage.save_charge(Charge(
            id=None, txid=pix.txid, amount_cents=amount_cents,
            description=description, copy_paste_code=pix.copy_paste_code,
            provider=self.psp.name,
        ))
        return t(self.lang, "charge_created", summary=charge.summary(),
                 code=charge.copy_paste_code)

    def _list_pending(self) -> str:
        pending = self.storage.pending_charges()
        if not pending:
            return t(self.lang, "no_pending")
        lines = "\n".join(c.summary() for c in pending)
        total = sum(c.amount_cents for c in pending)
        return (t(self.lang, "pending_header") + "\n" + lines + "\n\n" +
                t(self.lang, "total_due", total=format_brl(total)))

    def _daily_summary(self) -> str:
        now_local = datetime.now(self.tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_local.astimezone(timezone.utc).isoformat(timespec="seconds")
        paid = self.storage.paid_charges_since(start_utc)
        pending = self.storage.pending_charges()
        total = sum(c.amount_cents for c in paid)
        lines = "\n".join(c.summary() for c in paid) or t(self.lang, "none_yet")
        return t(self.lang, "daily_summary",
                 date=now_local.strftime("%d/%m/%Y"), count=len(paid),
                 lines=lines, total=format_brl(total), pending=len(pending))

    def _panel_link(self, sender: str) -> str:
        if not (self.public_url and self.dashboard_secret):
            return t(self.lang, "panel_disabled")
        token = make_token(self.dashboard_secret, sender)
        return t(self.lang, "panel_link",
                 url=f"{self.public_url}/painel?token={token}")

    def _cancel(self, charge_id: int) -> str:
        charge = self.storage.get_charge(charge_id)
        if charge is None:
            return t(self.lang, "cancel_not_found", id=charge_id)
        if charge.status.value != "pendente":
            return t(self.lang, "cancel_wrong_status", id=charge_id,
                     status=status_label(self.lang, charge.status.value))
        self.storage.mark_canceled(charge_id)
        return t(self.lang, "canceled", summary=charge.summary())

    # ── notificações da conciliação ─────────────────────────────────
    def notify_sellers(self, wa_client, message: str) -> None:
        for number in self.seller_numbers:
            wa_client.send_text(number, message)
