"""Simulação de usuários reais cometendo os erros que gente de verdade comete.

Cada teste é uma cena: vendedora Ana (autorizada), clientes João e Maria,
e um estranho. O objetivo é garantir que confusão de humano não vira
prejuízo nem silêncio do sistema.
"""

from fastapi.testclient import TestClient

from conftest import SELLER
from pixzap.matching import Reconciler
from pixzap.models import PaymentOutcome
from pixzap.server import create_app


def make_client(bot, storage, psp, wa):
    app = create_app(bot, Reconciler(storage), psp, wa, verify_token="tok")
    return TestClient(app)


def wa_text(text, sender=SELLER):
    return {"messages": [{"from": sender, "text": text}]}


def pay(client, psp, txid, cents, payer="", ref=""):
    payload = psp.payment_webhook_payload(txid, cents, payer_name=payer,
                                          payment_ref=ref)
    return client.post("/webhook/psp", json=payload,
                       headers={"x-fake-token": "segredo"})


# ── Cena 1: Ana manda o código para a pessoa ERRADA, e ela paga ──────
def test_wrong_person_pays_confirmation_shows_payer(bot, storage, psp, wa):
    """O dinheiro caiu de verdade, então confirma — mas a mensagem mostra
    QUEM pagou junto com a descrição do pedido, para Ana notar que o
    pagador (Maria) não bate com o pedido (João) antes de entregar."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João pedido 12"))
    charge = storage.pending_charges()[0]

    pay(client, psp, charge.txid, 15000, payer="Maria", ref="PAY1")
    confirmation = wa.last_message_to(SELLER)
    assert "Maria" in confirmation          # quem pagou
    assert "João pedido 12" in confirmation  # para qual pedido


# ── Cena 2: o MESMO código é pago DUAS vezes (pessoa errada + certa) ──
def test_second_real_payment_alerts_instead_of_silence(bot, storage, psp, wa):
    """QR estático aceita mais de um pagamento. O 2º pagamento REAL
    (payment_ref novo) não pode ser confundido com retry de webhook e
    engolido em silêncio: Ana precisa saber que tem dinheiro em dobro
    para devolver."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João pedido 12"))
    charge = storage.pending_charges()[0]

    r1 = pay(client, psp, charge.txid, 15000, payer="Maria", ref="PAY1")
    assert r1.json()["status"] == PaymentOutcome.CONFIRMED.value

    r2 = pay(client, psp, charge.txid, 15000, payer="João", ref="PAY2")
    assert r2.json()["status"] == PaymentOutcome.EXTRA.value
    alert = wa.last_message_to(SELLER)
    assert "SEGUNDO pagamento" in alert
    assert "JÁ ESTAVA PAGA" in alert


def test_webhook_retry_still_silent(bot, storage, psp, wa):
    """Retry do PSP (mesmo payment_ref) segue mudo — sem spam."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João"))
    charge = storage.pending_charges()[0]

    pay(client, psp, charge.txid, 15000, ref="PAY1")
    outbox_before = len(wa.outbox)
    r = pay(client, psp, charge.txid, 15000, ref="PAY1")  # retry idêntico
    assert r.json()["status"] == PaymentOutcome.DUPLICATE.value
    assert len(wa.outbox) == outbox_before


def test_mismatch_alerted_once_retry_silent(bot, storage, psp, wa):
    """Cliente pagou errado; o PSP reenvia o webhook 3x. Um alerta só."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João"))
    charge = storage.pending_charges()[0]

    pay(client, psp, charge.txid, 10000, ref="PAY1")
    outbox_after_first = len(wa.outbox)
    pay(client, psp, charge.txid, 10000, ref="PAY1")
    pay(client, psp, charge.txid, 10000, ref="PAY1")
    assert len(wa.outbox) == outbox_after_first  # só o primeiro alertou


# ── Cena 3: Ana digita o valor errado e o cliente paga o valor errado ─
def test_wrong_charge_amount_flow_cancel_and_recharge(bot, storage, psp, wa):
    """Ana queria 150 e digitou 15. Caminho de correção: cancelar e cobrar
    de novo. Se o cliente pagar os 15 ANTES do cancelamento, confirma
    (o combinado errado é problema comercial); depois do cancelamento,
    o pagamento tardio vira alerta de conferência manual."""
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 15 João pedido 12"))
    reply = wa.last_message_to(SELLER)
    assert "R$ 15,00" in reply  # o valor aparece na resposta para Ana conferir

    charge = storage.pending_charges()[0]
    client.post("/webhook/whatsapp", json=wa_text(f"cancelar {charge.id}"))
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João pedido 12"))

    # cliente paga o código VELHO (15) depois do cancelamento
    pay(client, psp, charge.txid, 1500, payer="João", ref="PAY1")
    alert = wa.last_message_to(SELLER)
    assert "cancelado" in alert

    # e o código novo confirma normalmente
    new_charge = storage.pending_charges()[0]
    pay(client, psp, new_charge.txid, 15000, payer="João", ref="PAY2")
    assert "PAGA" in wa.last_message_to(SELLER)


# ── Cena 4: duas cobranças do mesmo valor ao mesmo tempo ─────────────
def test_same_amount_charges_do_not_cross(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 João"))
    client.post("/webhook/whatsapp", json=wa_text("cobrar 150 Maria"))
    joao, maria = storage.pending_charges()

    pay(client, psp, maria.txid, 15000, payer="Maria", ref="P1")
    assert "Maria" in wa.last_message_to(SELLER)
    # a de João segue pendente: valor igual não confunde (match é por txid)
    assert [c.id for c in storage.pending_charges()] == [joao.id]


# ── Cena 5: comandos capengas de quem está aprendendo ─────────────────
def test_malformed_commands_teach_usage(bot):
    assert "cobrar 150" in bot.handle(SELLER, "cobrar")           # uso certo
    assert "transferir" in bot.handle(SELLER, "transferir 50")    # faltou chave
    assert "cancelar 12" in bot.handle(SELLER, "cancelar")        # faltou número
    assert "inválido" in bot.handle(SELLER, "confirmar 12").lower()
    assert "ajuda" in bot.handle(SELLER, "quero cobrar alguém")   # não-comando


# ── Cena 6: vendedor manda print/áudio para o bot ─────────────────────
def test_seller_sends_screenshot_gets_reminder(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp", json={
        "messages": [{"from": SELLER, "kind": "image"}]})
    reply = wa.last_message_to(SELLER)
    assert "print não é comprovante" in reply

    # estranho mandando imagem continua sem resposta (allowlist)
    outbox_before = len(wa.outbox)
    client.post("/webhook/whatsapp", json={
        "messages": [{"from": "5511000000000", "kind": "image"}]})
    assert len(wa.outbox) == outbox_before


# ── Cena 7: estranho tenta usar comandos ───────────────────────────────
def test_stranger_commands_ignored(bot, storage, psp, wa):
    client = make_client(bot, storage, psp, wa)
    client.post("/webhook/whatsapp",
                json=wa_text("cobrar 100 golpe", sender="5511000000000"))
    assert wa.outbox == []
    assert storage.pending_charges() == []
