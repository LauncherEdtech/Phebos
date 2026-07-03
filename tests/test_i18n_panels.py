"""i18n, link mágico e painéis web."""

from fastapi.testclient import TestClient

from conftest import SELLER
from pixzap.auth import make_token, verify_token
from pixzap.bot import Bot
from pixzap.i18n import MESSAGES, t
from pixzap.matching import Reconciler
from pixzap.models import Charge, PaymentEvent
from pixzap.server import create_app

SECRET = "segredo-de-teste"


# ── i18n ────────────────────────────────────────────────────────────
def test_all_languages_have_all_keys():
    keys = set(MESSAGES["pt"])
    for lang, catalog in MESSAGES.items():
        assert set(catalog) == keys, f"catálogo '{lang}' difere do pt"


def test_bot_replies_in_english(storage, psp):
    bot = Bot(storage, psp, [SELLER], lang="en")
    assert "automatic Pix" in bot.handle(SELLER, "ajuda")
    assert "created" in bot.handle(SELLER, "cobrar 100 order 1")


def test_reconciler_confirms_in_spanish(storage, psp):
    storage.save_charge(Charge(id=None, txid="T1", amount_cents=5000,
                               description="pedido 1", copy_paste_code="X"))
    reconciler = Reconciler(storage, lang="es")
    result = reconciler.handle_payment(
        PaymentEvent(txid="T1", amount_cents=5000, provider="fake"), raw={})
    assert "confirmado" in result.seller_message
    assert "PAGADO" in result.seller_message


def test_unknown_language_falls_back_to_pt():
    assert t("de", "no_pending") == t("pt", "no_pending")


# ── link mágico ─────────────────────────────────────────────────────
def test_token_roundtrip():
    token = make_token(SECRET, SELLER)
    assert verify_token(SECRET, token) == SELLER


def test_token_expired():
    token = make_token(SECRET, SELLER, ttl_seconds=-1)
    assert verify_token(SECRET, token) is None


def test_token_tampered():
    token = make_token(SECRET, SELLER)
    assert verify_token(SECRET, token[:-2] + "xx") is None
    assert verify_token("outro-segredo", token) is None
    assert verify_token(SECRET, "lixo") is None


def test_bot_panel_command(storage, psp):
    bot = Bot(storage, psp, [SELLER], public_url="https://pixzap.app",
              dashboard_secret=SECRET)
    reply = bot.handle(SELLER, "painel")
    assert "https://pixzap.app/painel?token=" in reply

    bot_sem_url = Bot(storage, psp, [SELLER])
    assert "não está configurado" in bot_sem_url.handle(SELLER, "painel")


# ── painéis pelo servidor ───────────────────────────────────────────
def make_client(bot, storage, psp, wa, **kwargs):
    return TestClient(create_app(bot, Reconciler(storage), psp, wa, **kwargs))


def test_seller_panel_requires_valid_token(storage, psp, wa):
    bot = Bot(storage, psp, [SELLER], public_url="https://x", dashboard_secret=SECRET)
    client = make_client(bot, storage, psp, wa, dashboard_secret=SECRET)

    bot.handle(SELLER, "cobrar 150 João pedido 1")
    token = make_token(SECRET, SELLER)

    resp = client.get("/painel", params={"token": token})
    assert resp.status_code == 200
    assert "João pedido 1" in resp.text
    assert "R$ 150,00" in resp.text

    assert client.get("/painel", params={"token": "invalido"}).status_code == 403
    assert client.get("/painel").status_code == 403
    # token válido mas de número que não é vendedor → recusado
    stranger = make_token(SECRET, "5511000000000")
    assert client.get("/painel", params={"token": stranger}).status_code == 403


def test_admin_panel_requires_token(storage, psp, wa):
    bot = Bot(storage, psp, [SELLER])
    client = make_client(bot, storage, psp, wa, admin_token="admin-secreto")

    bot.handle(SELLER, "cobrar 99,90 Maria")
    assert client.get("/admin").status_code == 403
    assert client.get("/admin", params={"token": "errado"}).status_code == 403

    resp = client.get("/admin", params={"token": "admin-secreto"})
    assert resp.status_code == 200
    assert "R$ 99,90" in resp.text
    assert "Maria" in resp.text


def test_admin_disabled_without_token(storage, psp, wa):
    bot = Bot(storage, psp, [SELLER])
    client = make_client(bot, storage, psp, wa)  # sem admin_token
    assert client.get("/admin", params={"token": ""}).status_code == 403
