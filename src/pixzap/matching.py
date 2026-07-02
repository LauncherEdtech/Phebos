"""Motor de conciliação determinístico — o coração do PixZap.

Regra de ouro (nunca enfraquecer): uma cobrança só vira "paga" quando o
webhook autenticado do PSP confirma o dinheiro. Nada de screenshot, nada
de "já paguei", nada de decisão por IA. Só código e centavos exatos.
"""

from .models import (Charge, ChargeStatus, PaymentEvent, PaymentOutcome,
                     ReconcileResult, format_brl)
from .storage import Storage


class Reconciler:
    def __init__(self, storage: Storage):
        self.storage = storage

    def handle_payment(self, event: PaymentEvent, raw: dict) -> ReconcileResult:
        """Processa um pagamento confirmado pelo PSP e devolve o veredito."""
        # 1. Idempotência: webhook repetido não gera nova confirmação
        if self.storage.has_confirmed_payment(event.provider, event.txid):
            return ReconcileResult(
                outcome=PaymentOutcome.DUPLICATE,
                charge=self.storage.get_charge_by_txid(event.txid),
                seller_message="",  # silencioso: nada de spam por retry de webhook
            )

        charge = self.storage.get_charge_by_txid(event.txid)

        # 2. Pix caiu sem cobrança associada → avisa, mas registra
        if charge is None:
            self.storage.record_payment(event, PaymentOutcome.UNMATCHED.value, None, raw)
            payer = f" de {event.payer_name}" if event.payer_name else ""
            return ReconcileResult(
                outcome=PaymentOutcome.UNMATCHED,
                charge=None,
                seller_message=(
                    f"⚠️ Recebi um Pix de {format_brl(event.amount_cents)}{payer} "
                    f"sem cobrança associada (txid {event.txid}). "
                    "Confira no app do banco antes de entregar qualquer pedido."
                ),
            )

        # 3. Valor divergente → NÃO quita a cobrança; alerta o vendedor
        if event.amount_cents != charge.amount_cents:
            self.storage.record_payment(event, PaymentOutcome.MISMATCH.value, charge.id, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.MISMATCH,
                charge=charge,
                seller_message=(
                    f"⚠️ Valor divergente na cobrança {charge.summary()}: "
                    f"esperado {format_brl(charge.amount_cents)}, "
                    f"recebido {format_brl(event.amount_cents)}. "
                    "A cobrança segue PENDENTE — confira antes de entregar."
                ),
            )

        # 4. Cobrança já finalizada (pagamento tardio de algo cancelado etc.)
        if charge.status != ChargeStatus.PENDING:
            self.storage.record_payment(event, PaymentOutcome.UNMATCHED.value, charge.id, raw)
            return ReconcileResult(
                outcome=PaymentOutcome.UNMATCHED,
                charge=charge,
                seller_message=(
                    f"⚠️ Pix de {format_brl(event.amount_cents)} recebido para a "
                    f"cobrança {charge.summary()}, que está '{charge.status.value}'. "
                    "Confira manualmente."
                ),
            )

        # 5. Tudo bateu → confirma
        self.storage.record_payment(event, PaymentOutcome.CONFIRMED.value, charge.id, raw)
        self.storage.mark_paid(charge.id)
        payer = f" de {event.payer_name}" if event.payer_name else ""
        return ReconcileResult(
            outcome=PaymentOutcome.CONFIRMED,
            charge=charge,
            seller_message=(
                f"✅ Pix de {format_brl(event.amount_cents)}{payer} confirmado!\n"
                f"Cobrança {charge.summary()} está PAGA. Pode liberar o pedido. 🎉"
            ),
        )
