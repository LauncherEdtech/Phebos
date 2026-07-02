"""Cliente de WhatsApp fake — guarda as mensagens enviadas numa lista."""

from typing import List

from .base import IncomingMessage, WhatsAppClient


class FakeWhatsApp(WhatsAppClient):
    def __init__(self):
        self.outbox: List[tuple[str, str]] = []  # (destino, texto)

    def send_text(self, to: str, text: str) -> None:
        self.outbox.append((to, text))

    def parse_incoming(self, payload: dict) -> List[IncomingMessage]:
        # Formato simples para testes: {"messages": [{"from": ..., "text": ...}]}
        return [IncomingMessage(sender=str(m["from"]), text=str(m["text"]))
                for m in payload.get("messages", [])]

    # ── auxiliares de teste ─────────────────────────────────────────
    def last_message_to(self, number: str) -> str:
        for to, text in reversed(self.outbox):
            if to == number:
                return text
        return ""
