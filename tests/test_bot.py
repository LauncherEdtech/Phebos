"""Comandos do vendedor no chat."""

from conftest import SELLER


def test_unknown_number_is_ignored(bot):
    assert bot.handle("5511000000000", "cobrar 100") is None


def test_help(bot):
    reply = bot.handle(SELLER, "ajuda")
    assert "cobrar" in reply
    assert "screenshot" in reply  # o aviso anti-golpe faz parte do produto


def test_cobrar_creates_charge_with_copy_paste(bot, storage):
    reply = bot.handle(SELLER, "cobrar 89,90 Maria pedido 7")
    assert "R$ 89,90" in reply
    assert "FAKEPIX" in reply  # copia-e-cola presente
    pending = storage.pending_charges()
    assert len(pending) == 1
    assert pending[0].amount_cents == 8990
    assert pending[0].description == "Maria pedido 7"


def test_cobrar_invalid_amount(bot, storage):
    reply = bot.handle(SELLER, "cobrar abc")
    assert "inválido" in reply.lower()
    assert storage.pending_charges() == []


def test_pendentes_and_cancelar(bot):
    bot.handle(SELLER, "cobrar 100 pedido A")
    bot.handle(SELLER, "cobrar 50 pedido B")
    reply = bot.handle(SELLER, "pendentes")
    assert "pedido A" in reply and "pedido B" in reply
    assert "R$ 150,00" in reply  # total a receber

    reply = bot.handle(SELLER, "cancelar 1")
    assert "cancelada" in reply
    reply = bot.handle(SELLER, "pendentes")
    assert "pedido A" not in reply


def test_unknown_command(bot):
    reply = bot.handle(SELLER, "bom dia grupo")
    assert "ajuda" in reply.lower()
