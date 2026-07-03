"""2ª rodada da simulação de usuários (catálogo completo em
docs/simulacao-100-jornadas.md) — cada teste reproduz uma cena que falhou."""

from conftest import SELLER
from pixzap.bot import Bot
from pixzap.matching import Reconciler
from pixzap.models import PaymentEvent, PaymentOutcome
from pixzap.psp.fake import FakePsp


class BrokenPsp(FakePsp):
    """Simula PSP fora do ar."""

    def create_charge(self, amount_cents, description):
        raise ConnectionError("timeout")

    def get_balance(self):
        raise ConnectionError("timeout")


# ── J13: PSP fora do ar não pode virar silêncio ───────────────────────
def test_psp_down_on_charge_replies_error(storage):
    bot = Bot(storage, BrokenPsp(), [SELLER])
    reply = bot.handle(SELLER, "cobrar 150 João")
    assert "Não consegui gerar a cobrança" in reply
    assert storage.pending_charges() == []


def test_psp_down_on_balance_replies_error(storage):
    bot = Bot(storage, BrokenPsp(), [SELLER])
    assert "provedor de pagamento" in bot.handle(SELLER, "saldo")


# ── J7: duplo toque cria cobrança em dobro → aviso ────────────────────
def test_double_tap_warns_about_identical_pending_charge(bot, storage):
    bot.handle(SELLER, "cobrar 150 João pedido 12")
    reply = bot.handle(SELLER, "cobrar 150 João pedido 12")
    assert "IGUAL pendente" in reply
    assert "cancelar 1" in reply
    assert len(storage.pending_charges()) == 2  # cria, mas avisa

    # valores iguais com descrição diferente NÃO é duplicata
    reply = bot.handle(SELLER, "cobrar 150 Maria pedido 13")
    assert "IGUAL" not in reply


# ── J4/J5: mensagens em várias linhas e com pontuação ─────────────────
def test_multiline_charge_message(bot, storage):
    reply = bot.handle(SELLER, "cobrar 150\nJoão pedido 12\nentregar sábado")
    assert "criada" in reply
    charge = storage.pending_charges()[0]
    assert charge.amount_cents == 15000
    assert "João pedido 12 entregar sábado" in charge.description


def test_punctuation_and_variants(bot):
    assert "PixZap" in bot.handle(SELLER, "Ajuda!")
    assert "PixZap" in bot.handle(SELLER, "oi!!")
    assert bot.handle(SELLER, "pendente") == bot.handle(SELLER, "Pendentes.")
    assert "Resumo" in bot.handle(SELLER, "resumo")


# ── J9: descrição gigante é aparada ───────────────────────────────────
def test_huge_description_is_trimmed(bot, storage):
    bot.handle(SELLER, "cobrar 150 " + "pedido enorme " * 50)
    charge = storage.pending_charges()[0]
    assert len(charge.description) <= 120


# ── J31: pagou errado, depois pagou certo (mesmo código) ──────────────
def test_mismatch_then_correct_payment_confirms(storage, reconciler):
    from pixzap.models import Charge
    charge = storage.save_charge(Charge(
        id=None, txid="T1", amount_cents=15000, description="João",
        copy_paste_code="X"))

    wrong = PaymentEvent(txid="T1", amount_cents=10000, provider="fake",
                         payment_ref="P1")
    assert reconciler.handle_payment(wrong, {}).outcome == PaymentOutcome.MISMATCH

    right = PaymentEvent(txid="T1", amount_cents=15000, provider="fake",
                         payment_ref="P2")
    result = reconciler.handle_payment(right, {})
    assert result.outcome == PaymentOutcome.CONFIRMED
    assert storage.get_charge(charge.id).status.value == "pago"


# ── J44: um vendedor não confirma a transferência do outro ────────────
def test_transfer_confirmation_is_per_sender(storage, psp):
    import re
    seller_b = "5511888887777"
    bot = Bot(storage, psp, [SELLER, seller_b],
              transfer_daily_limit_cents=100_000)
    reply = bot.handle(SELLER, "transferir 50 pix chave@x.com")
    code = re.search(r"confirmar (\d{6})", reply).group(1)
    # o colega de equipe tenta confirmar com o código do outro
    assert "inválido" in bot.handle(seller_b, f"confirmar {code}").lower()
    assert psp.transfers == []
