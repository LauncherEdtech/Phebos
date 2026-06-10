import json

from phebos.brokers.alpaca import AlpacaBroker
from phebos.brokers.binance import BinanceBroker
from phebos.schemas import OrderDecision


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def klines(n, price=100.0):
    return [[1717000000000 + i * 3600_000, str(price), str(price + 1),
             str(price - 1), str(price), "1000", 0, 0, 0, 0, 0, 0] for i in range(n)]


class FakeBinanceSession:
    headers: dict = {}

    def __init__(self):
        self.requests = []

    def get(self, url, params=None, timeout=None):
        self.requests.append((url, params))
        if "ticker/24hr" in url:
            return FakeResp({"lastPrice": "100.0", "priceChangePercent": "2.5"})
        if "klines" in url:
            return FakeResp(klines({"1h": 48, "4h": 30, "1d": 30}[params["interval"]]))
        if "ticker/price" in url:
            return FakeResp({"price": "100.0"})
        raise AssertionError(url)

    def request(self, method, url, params=None, timeout=None):
        self.requests.append((method, url, params))
        if "account" in url:
            return FakeResp({"balances": [
                {"asset": "USDT", "free": "500", "locked": "0"},
                {"asset": "BTC", "free": "0.01", "locked": "0"},
                {"asset": "DUST", "free": "0", "locked": "0"},
            ]})
        if "order" in url:
            return FakeResp({"orderId": 4321})
        raise AssertionError(url)


def test_binance_snapshot_multi_timeframe():
    b = BinanceBroker("k", "s", live=False)
    b.session = FakeBinanceSession()
    snap = b.snapshot(["BTCUSDT"])
    sym = snap.symbols[0]
    assert len(sym.candles) == 48 and len(sym.candles_4h) == 30 and len(sym.candles_1d) == 30
    assert sym.last_price == 100.0
    assert snap.cash_usd == 500.0
    assert snap.positions[0].symbol == "BTCUSDT"
    assert abs(snap.equity_usd - 501.0) < 1e-6  # 500 caixa + 0.01×100


def test_binance_execute_assina_e_usa_quote_qty():
    b = BinanceBroker("k", "s", live=False)
    fake = FakeBinanceSession()
    b.session = fake
    order = OrderDecision(symbol="BTCUSDT", side="buy", notional_usd=45.678,
                          confidence="high", rationale="t")
    executed = b.execute(order)
    assert executed.broker_order_id == "4321"
    method, url, params = fake.requests[-1]
    assert method == "POST" and params["quoteOrderQty"] == 45.68
    assert "signature" in params and "timestamp" in params


def test_binance_testnet_vs_live_url():
    assert "testnet" in BinanceBroker("k", "s", live=False).base_url
    assert "testnet" not in BinanceBroker("k", "s", live=True).base_url


def bars(n, price=200.0):
    return [{"t": f"2026-06-0{(i % 9) + 1}T00:00:00Z", "o": price, "h": price + 1,
             "l": price - 1, "c": price, "v": 5000} for i in range(n)]


class FakeAlpacaSession:
    headers: dict = {}

    def __init__(self):
        self.posts = []

    def get(self, url, params=None, timeout=None):
        if "clock" in url:
            return FakeResp({"is_open": True})
        if "/v2/stocks/bars" in url:
            tf = params["timeframe"]
            n = {"1Hour": 48, "4Hour": 30, "1Day": 30}[tf]
            return FakeResp({"bars": {"AAPL": bars(n)}})
        if "account" in url:
            return FakeResp({"equity": "10000", "cash": "4000"})
        if "positions" in url:
            return FakeResp([{"symbol": "AAPL", "qty": "10", "avg_entry_price": "190",
                              "market_value": "2000", "unrealized_pl": "100"}])
        raise AssertionError(url)

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        return FakeResp({"id": "alp-1"})


def test_alpaca_snapshot_multi_timeframe():
    a = AlpacaBroker("k", "s", live=False)
    a.session = FakeAlpacaSession()
    assert a.is_market_open()
    snap = a.snapshot(["AAPL"])
    sym = snap.symbols[0]
    assert len(sym.candles) == 48 and len(sym.candles_4h) == 30 and len(sym.candles_1d) == 30
    assert snap.equity_usd == 10000.0
    assert snap.positions[0].avg_price == 190.0


def test_alpaca_execute_notional():
    a = AlpacaBroker("k", "s", live=False)
    fake = FakeAlpacaSession()
    a.session = fake
    order = OrderDecision(symbol="AAPL", side="sell", notional_usd=99.999,
                          confidence="low", rationale="t")
    executed = a.execute(order)
    assert executed.broker_order_id == "alp-1"
    _, body = fake.posts[-1]
    assert body["notional"] == 100.0 and body["side"] == "sell"


def test_alpaca_paper_vs_live_url():
    assert "paper" in AlpacaBroker("k", "s", live=False).base_url
    assert "paper" not in AlpacaBroker("k", "s", live=True).base_url
