"""Modelos de domínio do PixZap.

Todo valor monetário é armazenado em **centavos (int)** — nunca float —
para que a conciliação seja exata ao centavo.
"""

import re
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
    EXTRA = "pagamento_extra"       # 2º pagamento REAL numa cobrança já paga


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Moedas suportadas: símbolo, separador decimal, separador de milhar,
# casas decimais exibidas. A moeda ativa é definida no config (currency).
CURRENCIES: dict[str, tuple[str, str, str, int]] = {
    "BRL": ("R$", ",", ".", 2),    # Brasil (Pix)
    "MXN": ("$", ".", ",", 2),     # México (SPEI)
    "ARS": ("$", ",", ".", 2),     # Argentina
    "COP": ("$", ",", ".", 0),     # Colômbia
    "NGN": ("₦", ".", ",", 2),     # Nigéria (transferência bancária)
    "KES": ("KSh", ".", ",", 2),   # Quênia (M-Pesa)
    "INR": ("₹", ".", ",", 2),     # Índia (UPI)
    "IDR": ("Rp", ",", ".", 0),    # Indonésia (QRIS)
    "USD": ("$", ".", ",", 2),
}
_active_currency = ["BRL"]

_MONEY_CHARS = re.compile(r"^[\d.,]+$")
_CURRENCY_PREFIXES = ("R$", "RP", "KSH", "₦", "₹", "$")


def set_currency(code: str) -> None:
    code = code.upper()
    if code not in CURRENCIES:
        raise ValueError(f"Moeda não suportada: {code} (opções: {', '.join(CURRENCIES)})")
    _active_currency[0] = code


def format_money(amount_cents: int) -> str:
    """Formata centavos na moeda ativa: 150050 em BRL → 'R$ 1.500,50'."""
    symbol, dec_sep, thou_sep, decimals = CURRENCIES[_active_currency[0]]
    sign = "-" if amount_cents < 0 else ""
    cents = abs(amount_cents)
    whole, frac = divmod(cents, 100)
    grouped = f"{whole:,}".replace(",", "\x00").replace("\x00", thou_sep)
    if decimals == 0:
        return f"{sign}{symbol} {grouped}"
    return f"{sign}{symbol} {grouped}{dec_sep}{frac:02d}"


# Alias histórico — todo o código formata pela moeda ativa.
format_brl = format_money


def parse_brl(text: str) -> Optional[int]:
    """Converte texto de valor em centavos, aceitando os dois estilos:
    '150', '150,50', 'R$ 1.500,50' (pt) e '150.50', '1,500.50' (en).

    Regra: o ÚLTIMO separador seguido de 1-2 dígitos é o decimal; separador
    seguido de 3 dígitos é milhar. Retorna None se não for um valor válido.
    """
    cleaned = text.strip().upper()
    for prefix in _CURRENCY_PREFIXES:
        cleaned = cleaned.removeprefix(prefix).strip()
    if not cleaned or not _MONEY_CHARS.match(cleaned):
        return None
    sep_positions = [i for i, ch in enumerate(cleaned) if ch in ".,"]
    if sep_positions:
        last = sep_positions[-1]
        tail = cleaned[last + 1:]
        if 1 <= len(tail) <= 2:            # decimal: 150,5 / 150.50
            int_part = re.sub(r"[.,]", "", cleaned[:last]) or "0"
            frac = tail.ljust(2, "0")
        elif len(tail) == 3:               # milhar: 1.500 / 1,500
            int_part = re.sub(r"[.,]", "", cleaned)
            frac = "00"
        else:
            return None
        if not (int_part.isdigit() and frac.isdigit()):
            return None
        value_cents = int(int_part) * 100 + int(frac)
    else:
        value_cents = int(cleaned) * 100
    if value_cents <= 0 or value_cents > 100_000_000_00:  # sanidade: 100 milhões
        return None
    return value_cents


parse_money = parse_brl


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
    """Pagamento confirmado pelo PSP (extraído de um webhook).

    txid identifica a COBRANÇA; payment_ref identifica ESTE pagamento.
    A distinção importa porque um QR estático pode ser pago mais de uma
    vez: mesmo txid, payment_ref diferente. Retry de webhook repete o
    payment_ref; pagamento novo de verdade traz um payment_ref novo.
    """

    txid: str
    amount_cents: int
    provider: str
    payer_name: str = ""
    payment_ref: str = ""           # vazio → usa o próprio txid
    received_at: str = field(default_factory=utcnow_iso)

    @property
    def ref(self) -> str:
        return self.payment_ref or self.txid


@dataclass
class ReconcileResult:
    """Veredito determinístico da conciliação + mensagem pronta ao vendedor."""

    outcome: PaymentOutcome
    charge: Optional[Charge]
    seller_message: str
