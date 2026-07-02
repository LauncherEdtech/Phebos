"""Adaptadores de envio/recebimento de mensagens no WhatsApp."""

from .base import IncomingMessage, WhatsAppClient
from .fake import FakeWhatsApp


def build_whatsapp(config) -> WhatsAppClient:
    """Instancia o cliente configurado (config: WhatsAppConfig)."""
    if config.provider == "fake":
        return FakeWhatsApp()
    if config.provider == "cloud":
        from .cloud import CloudApiWhatsApp
        return CloudApiWhatsApp(phone_number_id=config.phone_number_id,
                                access_token=config.access_token)
    raise ValueError(f"Provedor de WhatsApp desconhecido: {config.provider}")
