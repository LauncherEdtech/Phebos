"""Cliente da Cloud API: fallback para template quando a janela de 24h fecha."""

import pytest

from pixzap.whatsapp.cloud import CloudApiWhatsApp


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_client(responses, sent):
    client = CloudApiWhatsApp(phone_number_id="123", access_token="tok",
                              template_name="pixzap_notificacao")
    def fake_post(payload):
        sent.append(payload)
        return responses.pop(0)
    client._post = fake_post
    return client


def test_sends_plain_text_inside_window():
    sent = []
    client = make_client([FakeResponse(200)], sent)
    client.send_text("5511999998888", "Pix confirmado")
    assert len(sent) == 1
    assert sent[0]["type"] == "text"


def test_falls_back_to_template_when_window_closed():
    sent = []
    closed = FakeResponse(400, {"error": {"code": 131047, "message": "Re-engagement"}})
    client = make_client([closed, FakeResponse(200)], sent)
    client.send_text("5511999998888", "Pix de R$ 150,00 confirmado")
    assert len(sent) == 2
    assert sent[1]["type"] == "template"
    assert sent[1]["template"]["name"] == "pixzap_notificacao"
    params = sent[1]["template"]["components"][0]["parameters"]
    assert params[0]["text"] == "Pix de R$ 150,00 confirmado"


def test_other_errors_still_raise():
    sent = []
    denied = FakeResponse(401, {"error": {"code": 190, "message": "token"}})
    client = make_client([denied], sent)
    with pytest.raises(RuntimeError):
        client.send_text("5511999998888", "oi")
    assert len(sent) == 1  # não tenta template para erro que não é de janela


def test_no_template_configured_raises_on_closed_window():
    sent = []
    closed = FakeResponse(400, {"error": {"code": 131047}})
    client = CloudApiWhatsApp(phone_number_id="123", access_token="tok",
                              template_name="")
    client._post = lambda payload: (sent.append(payload), closed)[1]
    with pytest.raises(RuntimeError):
        client.send_text("5511999998888", "oi")
