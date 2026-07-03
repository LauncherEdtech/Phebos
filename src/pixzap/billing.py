"""Cobrança da assinatura do PixZap pelo próprio chat, em Pix.

Modelo: N cobranças grátis por mês (free_charges_per_month). Chegando
perto do limite o bot avisa; estourou sem pagar, novas cobranças ficam
bloqueadas até o vendedor pagar a mensalidade com *assinar* → Pix.

Arquitetura: a fatura é criada na NOSSA conta de PSP (credencial
separada da conta do cliente, que recebe as vendas dele). Como o webhook
da nossa conta não aponta para a instância do cliente, a confirmação é
por CONSULTA ATIVA ao PSP (comando *paguei*) — mesma fonte de verdade,
só que puxada em vez de empurrada. Screenshot continua não valendo.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .psp.base import PspClient
from .storage import Storage

log = logging.getLogger("pixzap.billing")


class BillingManager:
    def __init__(self, storage: Storage, psp: PspClient, price_cents: int,
                 free_quota: int, tz_name: str = "America/Sao_Paulo"):
        self.storage = storage
        self.psp = psp                    # PSP da NOSSA conta (não a do cliente)
        self.price_cents = price_cents
        self.free_quota = free_quota
        self.tz = ZoneInfo(tz_name)

    # ── período ─────────────────────────────────────────────────────
    def month_key(self) -> str:
        return datetime.now(self.tz).strftime("%Y-%m")

    def month_label(self) -> str:
        return datetime.now(self.tz).strftime("%m/%Y")

    def _month_start_utc(self) -> str:
        now = datetime.now(self.tz)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(timezone.utc).isoformat(timespec="seconds")

    # ── quota ───────────────────────────────────────────────────────
    def used(self) -> int:
        return self.storage.count_charges_since(self._month_start_utc())

    def remaining(self) -> int:
        return max(0, self.free_quota - self.used())

    def is_paid(self) -> bool:
        sub = self.storage.get_subscription(self.month_key())
        return bool(sub and sub["status"] == "pago")

    def blocked(self) -> bool:
        """Novas cobranças bloqueadas? Só se estourou a quota sem pagar."""
        return not self.is_paid() and self.remaining() <= 0

    # ── fatura ──────────────────────────────────────────────────────
    def get_or_create_invoice(self) -> dict:
        month = self.month_key()
        sub = self.storage.get_subscription(month)
        if sub:
            return sub
        pix = self.psp.create_charge(self.price_cents, f"PixZap {month}")
        self.storage.save_subscription(month, self.price_cents, pix.txid,
                                       pix.copy_paste_code, self.psp.name)
        log.info("Fatura da assinatura %s criada (%s)", month, pix.txid)
        return self.storage.get_subscription(month)

    def check_paid(self) -> Optional[bool]:
        """Consulta o PSP e marca o mês como pago se o Pix caiu.

        Retorna True (pagou), False (ainda não) ou None (sem fatura).
        """
        month = self.month_key()
        sub = self.storage.get_subscription(month)
        if sub is None:
            return None
        if sub["status"] == "pago":
            return True
        if self.psp.charge_paid(sub["txid"]):
            self.storage.mark_subscription_paid(month)
            log.info("Assinatura %s confirmada pelo PSP", month)
            return True
        return False
