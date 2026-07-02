"""Fluxo completo pelo servidor: cobrar no chat → webhook do PSP → confirmação."""

from fastapi.testclient import TestClient

from conftest import SELLER
from pixzap.matching import Reconciler
from pixzap.server import create_app


def make_client(bot, storage, psp, wa):
    app = create_app(bot, Reconciler(storage), psp, wa, verify_token="meu-token")
    return TestClient(app)


def wa_payload(text, sender=SELLER):
    return {"messages": [{"from": sender, "text": text}]}


def test_health(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_whatsapp_verification_handshake(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    resp = client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "meu-token",
        "hub.challenge": "12345"})
    assert resp.status_code == 200
    assert resp.text == "12345"

    resp = client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "errado",
        "hub.challenge": "12345"})
    assert resp.status_code == 403


def test_end_to_end_charge_and_payment(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)

    # 1. Vendedor cria a cobrança pelo chat
    resp = client.post("/webhook/whatsapp",
                       json=wa_payload("cobrar 150,00 João pedido 12"))
    assert resp.status_code == 200
    assert "copia-e-cola" in wa.last_message_to(SELLER)

    charge = storage.pending_charges()[0]

    # 2. Cliente diz que pagou (screenshot) — nada acontece, como deve ser
    assert storage.pending_charges()  # segue pendente

    # 3. O dinheiro cai de verdade: webhook autenticado do PSP
    payload = psp.payment_webhook_payload(charge.txid, 15000, payer_name="Maria")
    resp = client.post("/webhook/psp", json=payload,
                       headers={"x-fake-token": "segredo"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmado"

    # 4. Vendedor foi avisado e a cobrança está paga
    assert "confirmado" in wa.last_message_to(SELLER)
    assert storage.pending_charges() == []


def test_webhook_without_auth_is_rejected(bot, storage, psp, wa):
    """Regra de segurança: webhook não autenticado NUNCA confirma pagamento."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_payload("cobrar 100 pedido X"))
    charge = storage.pending_charges()[0]

    payload = psp.payment_webhook_payload(charge.txid, 10000)
    resp = client.post("/webhook/psp", json=payload)  # sem token
    assert resp.status_code == 401
    assert storage.pending_charges()  # cobrança segue pendente

    resp = client.post("/webhook/psp", json=payload,
                       headers={"x-fake-token": "forjado"})
    assert resp.status_code == 401
    assert storage.pending_charges()


def test_non_payment_event_is_ignored(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    resp = client.post("/webhook/psp", json={"event": "PAYMENT_CREATED"},
                       headers={"x-fake-token": "segredo"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignorado"
