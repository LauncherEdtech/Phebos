"""Carrega config.yaml + .env do PixZap.

Segredos (tokens de API) vêm SEMPRE de variáveis de ambiente — nunca do
YAML — para não vazarem em commit.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# Em Docker, PIXZAP_DATA_DIR=/app/data persiste o banco num volume
DATA_DIR = Path(os.environ.get("PIXZAP_DATA_DIR", str(ROOT)))
DB_PATH = DATA_DIR / "pixzap.db"


@dataclass
class WhatsAppConfig:
    provider: str = "fake"            # fake | cloud
    phone_number_id: str = ""         # ID do número na Cloud API (Meta)
    access_token: str = ""            # env: WHATSAPP_ACCESS_TOKEN
    verify_token: str = ""            # env: WHATSAPP_VERIFY_TOKEN (handshake do webhook)
    # Template utility aprovado (corpo com {{1}}) usado quando a janela de
    # 24h está fechada; vazio = sem fallback (mensagem é perdida e logada)
    template_name: str = "pixzap_notificacao"
    template_lang: str = "pt_BR"


@dataclass
class PspConfig:
    provider: str = "fake"            # fake | asaas | mercadopago
    asaas_api_key: str = ""           # env: ASAAS_API_KEY
    asaas_webhook_token: str = ""     # env: ASAAS_WEBHOOK_TOKEN (valida origem do webhook)
    asaas_sandbox: bool = True
    asaas_pix_key: str = ""           # chave Pix cadastrada no Asaas (QR estático)
    mp_access_token: str = ""         # env: MP_ACCESS_TOKEN
    mp_webhook_secret: str = ""       # env: MP_WEBHOOK_SECRET (assinatura x-signature)
    mp_payer_email: str = ""          # e-mail placeholder exigido pela API Pix do MP
    fake_webhook_token: str = "teste" # token do PSP fake (dev/testes)


@dataclass
class AssistantConfig:
    enabled: bool = False                 # assistente de IA (Gemini) no chat
    model: str = "gemini-2.5-flash-lite"
    financial_context: bool = True        # dados no contexto (exige opt-in do vendedor)
    api_key: str = ""                     # env: GEMINI_API_KEY


@dataclass
class PixzapConfig:
    # Números de WhatsApp autorizados a dar comandos ao bot (formato E.164
    # sem '+', ex.: 5511999998888). Mensagens de qualquer outro número são
    # ignoradas — regra de segurança, nunca enfraquecer.
    seller_numbers: List[str] = field(default_factory=list)
    timezone: str = "America/Sao_Paulo"
    language: str = "pt"              # idioma das respostas: pt | en | es | id
    currency: str = "BRL"             # moeda exibida (BRL, MXN, NGN, INR, IDR...)
    public_url: str = ""              # URL pública (https) — habilita o painel web
    # Limite diário (na moeda, ex.: 2000 = R$ 2.000) para o comando
    # "transferir". 0 = transferências pelo chat DESATIVADAS (padrão seguro).
    transfer_daily_limit: int = 0
    port: int = 8000
    admin_token: str = ""             # env: PIXZAP_ADMIN_TOKEN (habilita /admin)
    dashboard_secret: str = ""        # env: PIXZAP_DASHBOARD_SECRET (ou gerado)
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)
    psp: PspConfig = field(default_factory=PspConfig)
    assistant: AssistantConfig = field(default_factory=AssistantConfig)


def _dashboard_secret() -> str:
    """Segredo dos links mágicos: env ou gerado uma vez e persistido."""
    env_secret = os.environ.get("PIXZAP_DASHBOARD_SECRET", "")
    if env_secret:
        return env_secret
    secret_file = DATA_DIR / "dashboard.secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    import secrets
    generated = secrets.token_urlsafe(32)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(generated, encoding="utf-8")
    return generated


def load_config(path: str | None = None) -> PixzapConfig:
    load_dotenv(ROOT / ".env")
    config_path = Path(path or os.environ.get("PIXZAP_CONFIG", ROOT / "config.yaml"))
    raw: dict = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    wa_raw = raw.get("whatsapp", {})
    psp_raw = raw.get("psp", {})
    ai_raw = raw.get("assistant", {})
    cfg = PixzapConfig(
        seller_numbers=[str(n) for n in raw.get("seller_numbers", [])],
        timezone=raw.get("timezone", "America/Sao_Paulo"),
        language=str(raw.get("language", "pt")),
        currency=str(raw.get("currency", "BRL")).upper(),
        public_url=str(raw.get("public_url", "")),
        transfer_daily_limit=int(raw.get("transfer_daily_limit", 0)),
        port=int(raw.get("port", 8000)),
        admin_token=os.environ.get("PIXZAP_ADMIN_TOKEN", ""),
        dashboard_secret=_dashboard_secret(),
        whatsapp=WhatsAppConfig(
            provider=wa_raw.get("provider", "fake"),
            phone_number_id=str(wa_raw.get("phone_number_id", "")),
            access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
            verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", ""),
            template_name=str(wa_raw.get("template_name", "pixzap_notificacao")),
            template_lang=str(wa_raw.get("template_lang", "pt_BR")),
        ),
        psp=PspConfig(
            provider=psp_raw.get("provider", "fake"),
            asaas_api_key=os.environ.get("ASAAS_API_KEY", ""),
            asaas_webhook_token=os.environ.get("ASAAS_WEBHOOK_TOKEN", ""),
            asaas_sandbox=bool(psp_raw.get("asaas_sandbox", True)),
            asaas_pix_key=str(psp_raw.get("asaas_pix_key", "")),
            mp_access_token=os.environ.get("MP_ACCESS_TOKEN", ""),
            mp_webhook_secret=os.environ.get("MP_WEBHOOK_SECRET", ""),
            mp_payer_email=str(psp_raw.get("mp_payer_email", "")),
        ),
        assistant=AssistantConfig(
            enabled=bool(ai_raw.get("enabled", False)),
            model=str(ai_raw.get("model", "gemini-2.5-flash-lite")),
            financial_context=bool(ai_raw.get("financial_context", True)),
            api_key=os.environ.get("GEMINI_API_KEY", ""),
        ),
    )
    return cfg
