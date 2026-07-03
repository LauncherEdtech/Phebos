"""Assistente de IA: consentimento, contexto financeiro e fronteiras."""

from conftest import SELLER
from pixzap.assistant import GeminiAssistant, financial_summary
from pixzap.bot import Bot
from pixzap.models import Charge


class RecordingTransport:
    """Transporte fake: grava o payload enviado ao Gemini e responde fixo."""

    def __init__(self, reply="Resposta do auxiliar.", fail=False):
        self.reply = reply
        self.fail = fail
        self.payloads = []

    def __call__(self, payload):
        if self.fail:
            raise ConnectionError("gemini fora do ar")
        self.payloads.append(payload)
        return self.reply


def make_bot(storage, psp, transport):
    assistant = GeminiAssistant(api_key="", transport=transport)
    return Bot(storage, psp, [SELLER], assistant=assistant)


def system_text(payload):
    return payload["system_instruction"]["parts"][0]["text"]


def test_natural_language_goes_to_assistant(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    reply = bot.handle(SELLER, "como funciona o golpe do comprovante?")
    assert "Resposta do auxiliar." in reply
    assert len(transport.payloads) == 1


def test_commands_stay_deterministic_never_touch_ai(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    bot.handle(SELLER, "cobrar 150 João")
    bot.handle(SELLER, "pendentes")
    bot.handle(SELLER, "saldo")
    assert transport.payloads == []  # nenhum comando passou pela IA


def test_no_consent_no_financial_data_and_hint(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    bot.handle(SELLER, "cobrar 150 João pedido 12")

    reply = bot.handle(SELLER, "quanto vendi hoje?")
    system = system_text(transport.payloads[-1])
    assert "DADOS REAIS" not in system          # sem consentimento, sem dados
    assert "não autorizou" in system
    assert "assistente sim" in reply            # dica de como liberar


def test_consent_flow_enables_and_revokes_data(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    bot.handle(SELLER, "cobrar 150 João pedido 12")

    assert "Combinado" in bot.handle(SELLER, "assistente sim")
    bot.handle(SELLER, "quanto tenho a receber?")
    system = system_text(transport.payloads[-1])
    assert "DADOS REAIS" in system
    assert "João pedido 12" in system
    assert "R$ 150,00" in system

    assert "não olho mais" in bot.handle(SELLER, "assistente não")
    bot.handle(SELLER, "e agora?")
    assert "DADOS REAIS" not in system_text(transport.payloads[-1])


def test_prompt_carries_hard_rules(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    bot.handle(SELLER, "oi, o pix do joão caiu?")  # "oi..." não é saudação pura
    system = system_text(transport.payloads[-1])
    assert "NUNCA afirme que um pagamento foi confirmado" in system
    assert "NUNCA é prova de pagamento" in system
    assert "NÃO executa ações" in system


def test_assistant_failure_friendly_message(storage, psp):
    bot = make_bot(storage, psp, RecordingTransport(fail=True))
    reply = bot.handle(SELLER, "me ajuda com uma dúvida")
    assert "Não consegui pensar agora" in reply


def test_stranger_never_reaches_assistant(storage, psp):
    transport = RecordingTransport()
    bot = make_bot(storage, psp, transport)
    assert bot.handle("5511000000000", "quanto vendi hoje?") is None
    assert transport.payloads == []


def test_without_assistant_unknown_command_as_before(bot):
    assert "ajuda" in bot.handle(SELLER, "qualquer coisa aleatória").lower()


def test_financial_summary_contents(storage):
    storage.save_charge(Charge(id=None, txid="T1", amount_cents=15000,
                               description="João pedido 12",
                               copy_paste_code="X"))
    summary = financial_summary(storage, "America/Sao_Paulo")
    assert "Pendentes: 1" in summary
    assert "João pedido 12" in summary
