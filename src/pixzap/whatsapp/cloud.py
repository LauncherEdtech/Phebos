"""Cliente da WhatsApp Business Cloud API (oficial, Meta).

Usar a API oficial é decisão de produto: bibliotecas não oficiais
(Baileys etc.) derrubam o número — risco de plataforma inaceitável para
um produto cuja função é confirmar dinheiro.
"""

import logging
from typing import List

import requests

from .base import IncomingMessage, WhatsAppClient

log = logging.getLogger("pixzap.whatsapp")

GRAPH_URL = "https://graph.facebook.com/v21.0"


class CloudApiWhatsApp(WhatsAppClient):
    def __init__(self, phone_number_id: str, access_token: str):
        if not (phone_number_id and access_token):
            raise ValueError("Cloud API exige phone_number_id e WHATSAPP_ACCESS_TOKEN")
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    def send_text(self, to: str, text: str) -> None:
        resp = requests.post(
            f"{GRAPH_URL}/{self.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={"messaging_product": "whatsapp", "to": to,
                  "type": "text", "text": {"body": text}},
            timeout=30,
        )
        if resp.status_code >= 400:
            log.error("Falha ao enviar WhatsApp para %s: %s", to, resp.text)
        resp.raise_for_status()

    def parse_incoming(self, payload: dict) -> List[IncomingMessage]:
        messages: List[IncomingMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for msg in change.get("value", {}).get("messages", []):
                    if msg.get("type") == "text":
                        messages.append(IncomingMessage(
                            sender=str(msg.get("from", "")),
                            text=str(msg.get("text", {}).get("body", "")),
                        ))
        return messages
