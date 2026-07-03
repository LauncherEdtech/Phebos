"""Cliente da WhatsApp Business Cloud API (oficial, Meta).

Usar a API oficial é decisão de produto: bibliotecas não oficiais
(Baileys etc.) derrubam o número — risco de plataforma inaceitável para
um produto cuja função é confirmar dinheiro.

Custo (Brasil, 2026): respostas dentro da janela de serviço de 24h são
GRATUITAS; fora dela a Meta exige um template aprovado (utility,
US$ 0,008/msg). Este cliente tenta a mensagem normal e, se a Meta
responder com o erro 131047 (janela fechada), reenvia automaticamente
como template utility com o texto no corpo.
"""

import logging
from typing import List

import requests

from .base import IncomingMessage, WhatsAppClient

log = logging.getLogger("pixzap.whatsapp")

GRAPH_URL = "https://graph.facebook.com/v21.0"
# Erro da Meta quando a janela de 24h está fechada e é preciso template
REENGAGEMENT_ERROR_CODE = 131047


class CloudApiWhatsApp(WhatsAppClient):
    def __init__(self, phone_number_id: str, access_token: str,
                 template_name: str = "", template_lang: str = "pt_BR"):
        if not (phone_number_id and access_token):
            raise ValueError("Cloud API exige phone_number_id e WHATSAPP_ACCESS_TOKEN")
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        # Template utility aprovado no gerenciador da Meta, com um único
        # parâmetro {{1}} no corpo (ver GUIA.md → API oficial).
        self.template_name = template_name
        self.template_lang = template_lang

    def _post(self, payload: dict) -> requests.Response:
        return requests.post(
            f"{GRAPH_URL}/{self.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json=payload,
            timeout=30,
        )

    def send_text(self, to: str, text: str) -> None:
        resp = self._post({"messaging_product": "whatsapp", "to": to,
                           "type": "text", "text": {"body": text}})
        if resp.status_code < 400:
            return
        if self._window_closed(resp) and self.template_name:
            log.info("Janela de 24h fechada para %s — enviando via template", to)
            self._send_template(to, text)
            return
        log.error("Falha ao enviar WhatsApp para %s: %s", to, resp.text)
        resp.raise_for_status()

    @staticmethod
    def _window_closed(resp: requests.Response) -> bool:
        try:
            return resp.json()["error"]["code"] == REENGAGEMENT_ERROR_CODE
        except Exception:
            return False

    def _send_template(self, to: str, text: str) -> None:
        resp = self._post({
            "messaging_product": "whatsapp", "to": to, "type": "template",
            "template": {
                "name": self.template_name,
                "language": {"code": self.template_lang},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": text}],
                }],
            },
        })
        if resp.status_code >= 400:
            log.error("Falha no template para %s: %s", to, resp.text)
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
