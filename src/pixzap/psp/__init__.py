"""Adaptadores de PSP (provedores de pagamento Pix)."""

from .base import PixCharge, PspClient
from .fake import FakePsp


def build_psp(config) -> PspClient:
    """Instancia o PSP configurado (config: PspConfig)."""
    if config.provider == "fake":
        return FakePsp(webhook_token=config.fake_webhook_token)
    if config.provider == "asaas":
        from .asaas import AsaasPsp
        return AsaasPsp(api_key=config.asaas_api_key,
                        webhook_token=config.asaas_webhook_token,
                        sandbox=config.asaas_sandbox,
                        pix_key=config.asaas_pix_key)
    if config.provider == "mercadopago":
        from .mercadopago import MercadoPagoPsp
        return MercadoPagoPsp(access_token=config.mp_access_token,
                              webhook_secret=config.mp_webhook_secret,
                              payer_email=config.mp_payer_email or "cliente@pixzap.app")
    raise ValueError(f"PSP desconhecido: {config.provider}")
