"""Contrato dos clientes de WhatsApp."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class IncomingMessage:
    sender: str   # número E.164 sem '+', ex.: 5511999998888
    text: str


class WhatsAppClient(ABC):
    @abstractmethod
    def send_text(self, to: str, text: str) -> None:
        """Envia uma mensagem de texto para o número informado."""

    @abstractmethod
    def parse_incoming(self, payload: dict) -> List[IncomingMessage]:
        """Extrai mensagens de texto recebidas do payload do webhook."""
