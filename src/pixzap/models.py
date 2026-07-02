"""Modelos de domínio do PixZap.

Todo valor monetário é armazenado em **centavos (int)** — nunca float —
para que a conciliação seja exata ao centavo.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ChargeStatus(str, Enum):
    PENDING = "pendente"
    PAID = "pago"
    CANCELED = "cancelado"


class PaymentOutcome(str, Enum):
    """Resultado da conciliação de um pagamento recebido via webhook."""

    CONFIRMED = "confirmado"        # bateu txid + valor → cobrança quitada
    DUPLICATE = "duplicado"         # webhook repetido → ignorado (idempotência)
    MISMATCH = "valor_divergente"   # txid conhecido, valor diferente do cobrado
    UNMATCHED = "sem_cobranca"      # Pix caiu sem cobrança associada


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_brl(amount_cents: int) -> str:
    """Formata centavos como moeda brasileira: 150050 → 'R$ 1.500,50'."""
    sign = "-" if amount_cents < 0 else ""
    cents = abs(amount_cents)
    reais, resto = divmod(cents, 100)
    thousands = f"{reais:,}".replace(",", ".")  # separador de milhar pt-BR
    return f"{sign}R$ {thousands},{resto:02d}"


def parse_brl(text: str) -> Optional[int]:
    """Converte texto de valor em centavos: '150', '150,50', 'R$ 1.500,50'.

    Retorna None se não for um valor válido.
    """
    cleaned = text.strip().upper().removeprefix("R$").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value <= 0 or value > 1_000_000_00:  # limite de sanidade: R$ 100 milhões
        return None
    return round(value * 100)


@dataclass
class Charge:
    """Uma cobrança Pix criada pelo vendedor no chat."""

    id: Optional[int]
    txid: str                     # identificador da transação no PSP
    amount_cents: int
    description: str              # texto livre do vendedor (cliente/pedido)
    copy_paste_code: str          # Pix copia-e-cola para enviar ao cliente
    status: ChargeStatus = ChargeStatus.PENDING
    provider: str = "fake"
    created_at: str = field(default_factory=utcnow_iso)
    paid_at: Optional[str] = None

    def summary(self) -> str:
        return f"#{self.id} • {format_brl(self.amount_cents)} • {self.description or 'sem descrição'}"


@dataclass
class PaymentEvent:
    """Pagamento confirmado pelo PSP (extraído de um webhook)."""

    txid: str
    amount_cents: int
    provider: str
    payer_name: str = ""
    received_at: str = field(default_factory=utcnow_iso)


@dataclass
class ReconcileResult:
    """Veredito determinístico da conciliação + mensagem pronta ao vendedor."""

    outcome: PaymentOutcome
    charge: Optional[Charge]
    seller_message: str
