"""Ponto de entrada: monta as dependências e sobe o servidor."""

import logging

import uvicorn

from .bot import Bot
from .config import DB_PATH, load_config
from .matching import Reconciler
from .psp import build_psp
from .server import create_app
from .storage import Storage
from .whatsapp import build_whatsapp

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("pixzap")


def build() -> tuple:
    config = load_config()
    if not config.seller_numbers:
        log.warning("Nenhum número de vendedor configurado (seller_numbers) — "
                    "o bot vai ignorar todas as mensagens.")
    storage = Storage(DB_PATH)
    psp = build_psp(config.psp)
    wa_client = build_whatsapp(config.whatsapp)
    bot = Bot(storage, psp, config.seller_numbers, config.timezone)
    reconciler = Reconciler(storage)
    app = create_app(bot, reconciler, psp, wa_client,
                     verify_token=config.whatsapp.verify_token)
    return app, config


def run() -> None:
    app, config = build()
    log.info("PixZap no ar — PSP: %s | WhatsApp: %s | porta %s",
             config.psp.provider, config.whatsapp.provider, config.port)
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    run()
