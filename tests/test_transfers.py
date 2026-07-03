"""Saldo e transferências pelo chat: código de confirmação, limite, auditoria."""

import re

from conftest import SELLER
from pixzap.bot import Bot
from pixzap.psp.fake import FakePsp


def make_bot(storage, psp, limit_cents=500_000):
    return Bot(storage, psp, [SELLER], transfer_daily_limit_cents=limit_cents)


def extract_code(reply: str) -> str:
    return re.search(r"confirmar (\d{6})", reply).group(1)


def test_saldo(storage, psp):
    bot = make_bot(storage, psp)
    assert "R$ 990,00" in bot.handle(SELLER, "saldo")


def test_transfer_requires_confirmation_code(storage, psp):
    bot = make_bot(storage, psp)
    reply = bot.handle(SELLER, "transferir 200 pro pix: chave@email.com")
    assert "R$ 200,00" in reply and "chave@email.com" in reply
    assert psp.transfers == []  # nada executado ainda

    code = extract_code(reply)
    done = bot.handle(SELLER, f"confirmar {code}")
    assert "enviada" in done
    assert psp.transfers == [(20000, "chave@email.com")]
    assert psp.balance_cents == 99000 - 20000


def test_transfer_key_variants(storage, psp):
    bot = make_bot(storage, psp)
    for text, key in [
        ("transferir 10 pix 11999998888", "11999998888"),
        ("transferir 10 para chave@x.com", "chave@x.com"),
        ("transferir 10,50 pro pix: 123.456.789-00", "123.456.789-00"),
    ]:
        reply = bot.handle(SELLER, text)
        assert key in reply, text


def test_wrong_code_invalidates(storage, psp):
    bot = make_bot(storage, psp)
    bot.handle(SELLER, "transferir 50 pix chave@x.com")
    assert "inválido" in bot.handle(SELLER, "confirmar 000000").lower()
    # o código verdadeiro também morreu junto (proteção contra força bruta)
    assert psp.transfers == []


def test_daily_limit(storage, psp):
    bot = make_bot(storage, psp, limit_cents=30_000)  # R$ 300
    code = extract_code(bot.handle(SELLER, "transferir 250 pix a@b.c"))
    bot.handle(SELLER, f"confirmar {code}")
    reply = bot.handle(SELLER, "transferir 100 pix a@b.c")
    assert "Limite diário" in reply
    assert len(psp.transfers) == 1


def test_transfers_disabled_by_default(storage, psp):
    bot = Bot(storage, psp, [SELLER])  # sem limite configurado
    assert "desativadas" in bot.handle(SELLER, "transferir 10 pix a@b.c")


def test_insufficient_balance(storage):
    psp = FakePsp(balance_cents=1000)
    bot = make_bot(storage, psp)
    code = extract_code(bot.handle(SELLER, "transferir 200 pix a@b.c"))
    reply = bot.handle(SELLER, f"confirmar {code}")
    assert "não foi executada" in reply
    assert psp.transfers == []
