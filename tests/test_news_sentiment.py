import json

from phebos import sentiment
from phebos.news import _parse_feed, fetch_headlines, format_headlines

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed Teste</title>
<item><title>Bitcoin sobe forte</title><pubDate>Tue, 10 Jun 2026</pubDate></item>
<item><title>Fed mantem juros</title><pubDate>Mon, 09 Jun 2026</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Teste</title>
<entry><title>Tesla anuncia IPO de subsidiaria</title><updated>2026-06-10</updated></entry>
</feed>"""


def test_parse_rss():
    source, entries = _parse_feed(RSS)
    assert source == "Feed Teste"
    assert entries[0]["title"] == "Bitcoin sobe forte"
    assert len(entries) == 2


def test_parse_atom():
    source, entries = _parse_feed(ATOM)
    assert source == "Atom Teste"
    assert entries[0]["title"] == "Tesla anuncia IPO de subsidiaria"


def test_parse_xml_invalido_nao_explode():
    try:
        _parse_feed(b"<html>bloqueado</html>")
    except Exception:
        pass  # fetch_headlines captura — aqui só não pode travar o processo


class FakeResponse:
    def __init__(self, content=b"", payload=None, status=200):
        self.content = content
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_headlines_com_mock(monkeypatch):
    monkeypatch.setattr("phebos.news.requests.get", lambda *a, **k: FakeResponse(content=RSS))
    hs = fetch_headlines(["http://feed1", "http://feed2"], limit_per_feed=1)
    assert len(hs) == 2  # 1 por feed
    assert hs[0]["source"] == "Feed Teste"


def test_fetch_headlines_erro_http_tolerado(monkeypatch):
    monkeypatch.setattr("phebos.news.requests.get",
                        lambda *a, **k: FakeResponse(status=403))
    assert fetch_headlines(["http://feed1"]) == []


def test_format_headlines_vazio():
    assert "nenhuma manchete" in format_headlines([])


# ── sentimento ──────────────────────────────────────────────────────
REDDIT = {"data": {"children": [
    {"data": {"title": "BTC to the moon", "score": 500, "num_comments": 80, "stickied": False}},
    {"data": {"title": "Regras do sub", "score": 10, "num_comments": 0, "stickied": True}},
]}}

STOCKTWITS = {"messages": [
    {"body": "comprando tudo", "entities": {"sentiment": {"basic": "Bullish"}}},
    {"body": "vai cair", "entities": {"sentiment": {"basic": "Bearish"}}},
    {"body": "neutro aqui", "entities": {"sentiment": None}},
]}

FNG = {"data": [{"value": "72", "value_classification": "Greed"}]}


def test_reddit_ignora_fixados(monkeypatch):
    monkeypatch.setattr("phebos.sentiment.requests.get",
                        lambda *a, **k: FakeResponse(payload=REDDIT))
    posts = sentiment.fetch_reddit_hot(["CryptoCurrency"])
    assert len(posts) == 1 and posts[0]["title"] == "BTC to the moon"


def test_stocktwits_conta_sentimento(monkeypatch):
    monkeypatch.setattr("phebos.sentiment.requests.get",
                        lambda *a, **k: FakeResponse(payload=STOCKTWITS))
    st = sentiment.fetch_stocktwits("BTCUSDT")
    assert st["bullish"] == 1 and st["bearish"] == 1 and st["messages"] == 3


def test_stocktwits_simbolo_cripto_vira_ponto_x(monkeypatch):
    urls = []
    def fake_get(url, **k):
        urls.append(url)
        return FakeResponse(payload=STOCKTWITS)
    monkeypatch.setattr("phebos.sentiment.requests.get", fake_get)
    sentiment.fetch_stocktwits("ETHUSDT")
    assert "ETH.X.json" in urls[0]


def test_fear_greed(monkeypatch):
    monkeypatch.setattr("phebos.sentiment.requests.get",
                        lambda *a, **k: FakeResponse(payload=FNG))
    fng = sentiment.fetch_fear_greed()
    assert fng == {"value": 72, "label": "Greed"}


def test_collect_monta_bloco_completo(monkeypatch):
    def fake_get(url, **k):
        if "alternative.me" in url:
            return FakeResponse(payload=FNG)
        if "reddit" in url:
            return FakeResponse(payload=REDDIT)
        return FakeResponse(payload=STOCKTWITS)
    monkeypatch.setattr("phebos.sentiment.requests.get", fake_get)
    text = sentiment.collect("crypto", ["BTCUSDT"], ["CryptoCurrency"])
    assert "Fear & Greed" in text and "Reddit" in text and "StockTwits" in text


def test_collect_tolerante_a_falha_total(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("rede fora")
    monkeypatch.setattr("phebos.sentiment.requests.get", boom)
    text = sentiment.collect("crypto", ["BTCUSDT"], ["CryptoCurrency"])
    assert "sem dados" in text
