"""PSP fake para desenvolvimento e testes — sem rede externa.

Simula a criação de cobranças e permite gerar payloads de webhook como
se o dinheiro tivesse caído.
"""

import itertools
from typing import Mapping, Optional

from ..models import PaymentEvent
from .base import PixCharge, PspClient


class FakePsp(PspClient):
    name = "fake"
    supports_transfers = True

    def __init__(self, webhook_token: str = "teste", balance_cents: int = 99000):
        self.webhook_token = webhook_token
        self._counter = itertools.count(1)
        self.charges: dict[str, PixCharge] = {}
        self.balance_cents = balance_cents
        self.transfers: list[tuple[int, str]] = []  # (valor, chave)
        self.paid_charges: set[str] = set()         # txids pagos (billing)

    def get_balance(self) -> int:
        return self.balance_cents

    def charge_paid(self, txid: str) -> bool:
        return txid in self.paid_charges

    def mark_charge_paid(self, txid: str) -> None:
        """Auxiliar de teste: simula o Pix da fatura caindo."""
        self.paid_charges.add(txid)

    def transfer(self, amount_cents: int, pix_key: str, description: str = "") -> str:
        if amount_cents > self.balance_cents:
            raise ValueError("saldo insuficiente")
        self.balance_cents -= amount_cents
        self.transfers.append((amount_cents, pix_key))
        return f"TRF{len(self.transfers):06d}"

    def create_charge(self, amount_cents: int, description: str) -> PixCharge:
        txid = f"FAKE{next(self._counter):08d}"
        charge = PixCharge(
            txid=txid,
            copy_paste_code=f"00020126FAKEPIX{txid}5204000053039865802BR",
        )
        self.charges[txid] = charge
        return charge

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        return headers.get("x-fake-token", "") == self.webhook_token

    def parse_webhook(self, payload: dict) -> Optional[PaymentEvent]:
        if payload.get("event") != "PAYMENT_RECEIVED":
            return None
        return PaymentEvent(
            txid=str(payload.get("txid", "")),
            amount_cents=int(payload.get("amount_cents", 0)),
            provider=self.name,
            payer_name=str(payload.get("payer_name", "")),
            payment_ref=str(payload.get("payment_ref", "")),
        )

    # ── auxiliar de teste ───────────────────────────────────────────
    def payment_webhook_payload(self, txid: str, amount_cents: int,
                                payer_name: str = "",
                                payment_ref: str = "") -> dict:
        """Monta o payload que o PSP fake enviaria quando um Pix cai.

        payment_ref vazio simula PSP que só manda o txid; preenchido
        simula pagamento distinto no mesmo QR (ex.: QR estático pago 2x).
        """
        return {"event": "PAYMENT_RECEIVED", "txid": txid,
                "amount_cents": amount_cents, "payer_name": payer_name,
                "payment_ref": payment_ref}
