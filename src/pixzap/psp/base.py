"""Contrato que todo adaptador de PSP implementa."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional

from ..models import PaymentEvent


@dataclass
class PixCharge:
    """Cobrança Pix criada no PSP."""

    txid: str
    copy_paste_code: str   # o "Pix copia-e-cola" que o cliente usa para pagar


class PspClient(ABC):
    name: str = "base"

    @abstractmethod
    def create_charge(self, amount_cents: int, description: str) -> PixCharge:
        """Cria uma cobrança Pix e devolve txid + copia-e-cola."""

    @abstractmethod
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        """Valida que o webhook veio mesmo do PSP (token/assinatura).

        Regra de segurança: webhook reprovado aqui é DESCARTADO — nunca
        confirmar pagamento a partir de requisição não autenticada.
        """

    @abstractmethod
    def parse_webhook(self, payload: dict) -> Optional[PaymentEvent]:
        """Extrai um pagamento CONFIRMADO do payload; None se o evento
        não representa dinheiro que caiu (ex.: cobrança criada/expirada)."""
