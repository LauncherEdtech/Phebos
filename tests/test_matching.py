"""Conciliação determinística: confirmação, idempotência, divergência."""

from pixzap.models import Charge, ChargeStatus, PaymentEvent, PaymentOutcome


def make_charge(storage, txid="FAKE1", amount=15000, description="João pedido 1"):
    return storage.save_charge(Charge(
        id=None, txid=txid, amount_cents=amount, description=description,
        copy_paste_code="PIXCODE", provider="fake",
    ))


def event(txid="FAKE1", amount=15000, payer="Maria"):
    return PaymentEvent(txid=txid, amount_cents=amount, provider="fake",
                        payer_name=payer)


def test_payment_confirms_charge(storage, reconciler):
    charge = make_charge(storage)
    result = reconciler.handle_payment(event(), raw={})
    assert result.outcome == PaymentOutcome.CONFIRMED
    assert "R$ 150,00" in result.seller_message
    assert storage.get_charge(charge.id).status == ChargeStatus.PAID


def test_duplicate_webhook_is_idempotent(storage, reconciler):
    make_charge(storage)
    first = reconciler.handle_payment(event(), raw={})
    second = reconciler.handle_payment(event(), raw={})
    assert first.outcome == PaymentOutcome.CONFIRMED
    assert second.outcome == PaymentOutcome.DUPLICATE
    assert second.seller_message == ""  # sem spam de retry


def test_amount_mismatch_keeps_charge_pending(storage, reconciler):
    charge = make_charge(storage, amount=15000)
    result = reconciler.handle_payment(event(amount=10000), raw={})
    assert result.outcome == PaymentOutcome.MISMATCH
    assert "divergente" in result.seller_message.lower()
    assert storage.get_charge(charge.id).status == ChargeStatus.PENDING


def test_unknown_txid_alerts_seller(storage, reconciler):
    result = reconciler.handle_payment(event(txid="DESCONHECIDO"), raw={})
    assert result.outcome == PaymentOutcome.UNMATCHED
    assert "sem cobrança associada" in result.seller_message


def test_payment_for_canceled_charge_alerts(storage, reconciler):
    charge = make_charge(storage)
    storage.mark_canceled(charge.id)
    result = reconciler.handle_payment(event(), raw={})
    assert result.outcome == PaymentOutcome.UNMATCHED
    assert "cancelado" in result.seller_message
    assert storage.get_charge(charge.id).status == ChargeStatus.CANCELED
