"""Motor de conciliação determinístico — o coração do PixZap.

Regra de ouro (nunca enfraquecer): uma cobrança só vira "paga" quando o
webhook autenticado do PSP confirma o dinheiro. Nada de screenshot, nada
de "já paguei", nada de decisão por IA. Só código e centavos exatos.
"""

from .i18n import DEFAULT_LANG, status_label, t
from .models import (Charge, ChargeStatus, PaymentEvent, PaymentOutcome,
                     ReconcileResult, format_money)
from .storage import Storage


class Reconciler:
    def __init__(self, storage: Storage, lang: str = DEFAULT_LANG):
        self.storage = storage
        self.lang = lang

    def _payer(self, event: PaymentEvent) -> str:
        return t(self.lang, "payer_from", name=event.payer_name) if event.payer_name else ""

    def handle_payment(self, event: PaymentEvent, raw: dict) -> ReconcileResult:
        """Processa um pagamento confirmado pelo PSP e devolve o veredito."""
        # 1. Idempotência POR PAGAMENTO: o mesmo payment_ref já processado
        #    (com qualquer veredito) é retry de webhook → silêncio total.
        if self.storage.has_payment_ref(event.provider, event.ref):
            return ReconcileResult(
                outcome=PaymentOutcome.DUPLICATE,
                charge=self.storage.get_charge_by_txid(event.txid),
                seller_message="",  # silencioso: nada de spam por retry
            )

        charge = self.storage.get_charge_by_txid(event.txid)

        # 2. Pix caiu sem cobrança associada → avisa, mas registra
        if charge is None:
            self.storage.record_payment(event, PaymentOutcome.UNMATCHED.value, None, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.UNMATCHED,
                charge=None,
                seller_message=t(self.lang, "pay_unmatched",
                                 amount=format_money(event.amount_cents),
                                 payer=self._payer(event), txid=event.txid),
            )

        # 3. Cobrança JÁ PAGA recebendo pagamento novo (payment_ref inédito):
        #    é dinheiro real em duplicidade (QR estático pago 2x, cliente
        #    reaproveitando código antigo, pessoa errada pagando junto).
        #    Nunca ignorar em silêncio — o vendedor precisa devolver.
        if charge.status == ChargeStatus.PAID:
            self.storage.record_payment(event, PaymentOutcome.EXTRA.value, charge.id, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.EXTRA,
                charge=charge,
                seller_message=t(self.lang, "pay_extra",
                                 amount=format_money(event.amount_cents),
                                 payer=self._payer(event), summary=charge.summary()),
            )

        # 4. Cobrança cancelada recebendo pagamento tardio
        if charge.status != ChargeStatus.PENDING:
            self.storage.record_payment(event, PaymentOutcome.UNMATCHED.value, charge.id, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.UNMATCHED,
                charge=charge,
                seller_message=t(self.lang, "pay_wrong_status",
                                 amount=format_money(event.amount_cents),
                                 summary=charge.summary(),
                                 status=status_label(self.lang, charge.status.value)),
            )

        # 5. Valor divergente → NÃO quita a cobrança; alerta o vendedor
        if event.amount_cents != charge.amount_cents:
            self.storage.record_payment(event, PaymentOutcome.MISMATCH.value, charge.id, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.MISMATCH,
                charge=charge,
                seller_message=t(self.lang, "pay_mismatch",
                                 summary=charge.summary(),
                                 expected=format_money(charge.amount_cents),
                                 received=format_money(event.amount_cents)),
            )

        # 6. Tudo bateu → confirma
        self.storage.record_payment(event, PaymentOutcome.CONFIRMED.value, charge.id, raw)
        self.storage.mark_paid(charge.id)
        return ReconcileResult(
            outcome=PaymentOutcome.CONFIRMED,
            charge=charge,
            seller_message=t(self.lang, "pay_confirmed",
                             amount=format_money(event.amount_cents),
                             payer=self._payer(event), summary=charge.summary()),
        )
