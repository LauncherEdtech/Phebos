"""Binance spot via REST. Demo usa a testnet (https://testnet.binance.vision)."""

import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import List
from urllib.parse import urlencode

import requests

from ..schemas import Candle, MarketSnapshot, Position, SymbolData
from .base import Broker, ExecutedOrder

TESTNET_URL = "https://testnet.binance.vision"
LIVE_URL = "https://api.binance.com"

# Ativos de cotação tratados como caixa em USD
_STABLE = {"USDT", "USDC", "FDUSD", "BUSD"}


class BinanceBroker(Broker):
    market = "crypto"

    def __init__(self, api_key: str, api_secret: str, live: bool):
        self.base_url = LIVE_URL if live else TESTNET_URL
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.session = requests.Session()
        self.session.headers["X-MBX-APIKEY"] = api_key

    # ── HTTP ────────────────────────────────────────────────────────
    def _public(self, path: str, params: dict | None = None) -> dict | list:
        r = self.session.get(f"{self.base_url}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _signed(self, method: str, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        params["signature"] = hmac.new(self.api_secret, query.encode(), hashlib.sha256).hexdigest()
        r = self.session.request(method, f"{self.base_url}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # ── Broker ──────────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        return True  # cripto opera 24/7

    def _klines(self, symbol: str, interval: str, limit: int) -> list:
        raw = self._public("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [
            Candle(
                open_time=datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(),
                open=float(k[1]), high=float(k[2]), low=float(k[3]),
                close=float(k[4]), volume=float(k[5]),
            )
            for k in raw
        ]

    def snapshot(self, symbols: List[str]) -> MarketSnapshot:
        symbol_data = []
        prices: dict[str, float] = {}
        for sym in symbols:
            ticker = self._public("/api/v3/ticker/24hr", {"symbol": sym})
            prices[sym] = float(ticker["lastPrice"])
            symbol_data.append(SymbolData(
                symbol=sym,
                last_price=float(ticker["lastPrice"]),
                change_24h_pct=float(ticker["priceChangePercent"]),
                candles=self._klines(sym, "1h", 48),
                candles_4h=self._klines(sym, "4h", 30),
                candles_1d=self._klines(sym, "1d", 30),
            ))

        account = self._signed("GET", "/api/v3/account")
        cash = 0.0
        positions: list[Position] = []
        for bal in account["balances"]:
            qty = float(bal["free"]) + float(bal["locked"])
            if qty <= 0:
                continue
            asset = bal["asset"]
            if asset in _STABLE:
                cash += qty
                continue
            pair = f"{asset}USDT"
            price = prices.get(pair)
            if price is None:
                try:
                    price = float(self._public("/api/v3/ticker/price", {"symbol": pair})["price"])
                except requests.HTTPError:
                    continue  # ativo sem par USDT — ignorado no patrimônio
            positions.append(Position(
                symbol=pair, qty=qty, avg_price=0.0,
                market_value=qty * price, unrealized_pnl=0.0,
            ))

        equity = cash + sum(p.market_value for p in positions)
        return MarketSnapshot(
            market="crypto",
            timestamp=datetime.now(timezone.utc).isoformat(),
            equity_usd=equity,
            cash_usd=cash,
            positions=positions,
            symbols=symbol_data,
        )

    def execute(self, order) -> ExecutedOrder:
        resp = self._signed("POST", "/api/v3/order", {
            "symbol": order.symbol,
            "side": order.side.upper(),
            "type": "MARKET",
            "quoteOrderQty": round(order.notional_usd, 2),
        })
        return ExecutedOrder(order.symbol, order.side, order.notional_usd, str(resp["orderId"]))
