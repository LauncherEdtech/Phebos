"""Adaptador Mercado Pago — beta, validar no sandbox.

Cria pagamento Pix via `/v1/payments` e recebe webhooks do tipo `payment`.
Como o webhook do MP só traz o id, o adaptador consulta a API para saber o
status e o valor reais — nunca confia no corpo do webhook para confirmar.
A origem é validada pela assinatura HMAC do header `x-signature`.
"""

import hashlib
import hmac
import uuid
from typing import Mapping, Optional

import requests

from ..models import PaymentEvent
from .base import PixCharge, PspClient

BASE_URL = "https://api.mercadopago.com"


class MercadoPagoPsp(PspClient):
    name = "mercadopago"

    def __init__(self, access_token: str, webhook_secret: str,
                 payer_email: str = "cliente@pixzap.app"):
        if not access_token:
            raise ValueError("MP_ACCESS_TOKEN não configurado")
        if not webhook_secret:
            raise ValueError("MP_WEBHOOK_SECRET não configurado — sem ele "
                             "qualquer um poderia forjar confirmações de pagamento")
        self.access_token = access_token
        self.webhook_secret = webhook_secret
        self.payer_email = payer_email

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": str(uuid.uuid4())}

    def create_charge(self, amount_cents: int, description: str) -> PixCharge:
        payload = {
            "transaction_amount": amount_cents / 100,
            "payment_method_id": "pix",
            "description": description or "PixZap",
            "payer": {"email": self.payer_email},
        }
        resp = requests.post(f"{BASE_URL}/v1/payments", json=payload,
                             headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        code = data["point_of_interaction"]["transaction_data"]["qr_code"]
        return PixCharge(txid=str(data["id"]), copy_paste_code=code)

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        # Assinatura documentada: HMAC-SHA256 de
        # "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" com o secret
        signature = headers.get("x-signature", "")
        request_id = headers.get("x-request-id", "")
        parts = dict(p.strip().split("=", 1) for p in signature.split(",") if "=" in p)
        ts, v1 = parts.get("ts", ""), parts.get("v1", "")
        data_id = headers.get("x-data-id", "")  # preenchido pelo server a partir da query
        if not (ts and v1):
            return False
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected = hmac.new(self.webhook_secret.encode(), manifest.encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)

    def parse_webhook(self, payload: dict) -> Optional[PaymentEvent]:
        if payload.get("type") != "payment":
            return None
        payment_id = str(payload.get("data", {}).get("id", ""))
        if not payment_id:
            return None
        # Consulta a fonte da verdade: a própria API do MP
        resp = requests.get(f"{BASE_URL}/v1/payments/{payment_id}",
                            headers={"Authorization": f"Bearer {self.access_token}"},
                            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "approved":
            return None
        payer = data.get("payer", {}) or {}
        name = " ".join(filter(None, [payer.get("first_name"), payer.get("last_name")]))
        return PaymentEvent(
            txid=str(data["id"]),
            amount_cents=round(float(data["transaction_amount"]) * 100),
            provider=self.name,
            payer_name=name,
        )
