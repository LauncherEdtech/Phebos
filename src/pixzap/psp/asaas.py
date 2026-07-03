"""Adaptador Asaas (https://asaas.com) — beta, validar no sandbox.

Estratégia: QR Code Pix **estático com valor** via `/v3/pix/qrCodes/static`
(dispensa cadastro de cliente). Quando o Pix cai, o Asaas dispara o webhook
`PAYMENT_RECEIVED`; a origem é validada pelo token configurado no painel
(header `asaas-access-token`).
"""

from typing import Mapping, Optional

import requests

from ..models import PaymentEvent
from .base import PixCharge, PspClient

SANDBOX_URL = "https://api-sandbox.asaas.com/v3"
PRODUCTION_URL = "https://api.asaas.com/v3"


class AsaasPsp(PspClient):
    name = "asaas"
    supports_transfers = True  # beta: validar no sandbox

    def __init__(self, api_key: str, webhook_token: str, sandbox: bool = True,
                 pix_key: str = ""):
        if not api_key:
            raise ValueError("ASAAS_API_KEY não configurada")
        if not webhook_token:
            raise ValueError("ASAAS_WEBHOOK_TOKEN não configurado — sem ele "
                             "qualquer um poderia forjar confirmações de pagamento")
        self.api_key = api_key
        self.webhook_token = webhook_token
        self.pix_key = pix_key
        self.base_url = SANDBOX_URL if sandbox else PRODUCTION_URL

    def _headers(self) -> dict:
        return {"access_token": self.api_key, "Content-Type": "application/json"}

    def create_charge(self, amount_cents: int, description: str) -> PixCharge:
        payload = {
            "addressKey": self.pix_key,
            "description": description[:37] or "PixZap",
            "value": amount_cents / 100,
            "format": "ALL",
        }
        resp = requests.post(f"{self.base_url}/pix/qrCodes/static",
                             json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return PixCharge(txid=str(data["id"]), copy_paste_code=data["payload"])

    def get_balance(self) -> int:
        resp = requests.get(f"{self.base_url}/finance/balance",
                            headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return round(float(resp.json()["balance"]) * 100)

    def transfer(self, amount_cents: int, pix_key: str, description: str = "") -> str:
        payload = {"value": amount_cents / 100, "pixAddressKey": pix_key,
                   "operationType": "PIX", "description": description or "PixZap"}
        resp = requests.post(f"{self.base_url}/transfers", json=payload,
                             headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return str(resp.json()["id"])

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        return headers.get("asaas-access-token", "") == self.webhook_token

    def parse_webhook(self, payload: dict) -> Optional[PaymentEvent]:
        # PAYMENT_RECEIVED = dinheiro caiu; demais eventos não confirmam nada
        if payload.get("event") not in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"):
            return None
        payment = payload.get("payment", {})
        txid = str(payment.get("pixQrCodeId") or payment.get("id") or "")
        value = payment.get("value")
        if not txid or value is None:
            return None
        return PaymentEvent(
            txid=txid,
            amount_cents=round(float(value) * 100),
            provider=self.name,
            payer_name=str(payment.get("payerName", "") or ""),
        )
