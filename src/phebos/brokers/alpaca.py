"""Alpaca (ações dos EUA) via REST. Demo usa paper trading."""

from datetime import datetime, timezone
from typing import List

import requests

from ..schemas import Candle, MarketSnapshot, Position, SymbolData
from .base import Broker, ExecutedOrder

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


class AlpacaBroker(Broker):
    market = "stocks"

    def __init__(self, api_key: str, api_secret: str, live: bool):
        self.base_url = LIVE_URL if live else PAPER_URL
        self.session = requests.Session()
        self.session.headers.update({
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        })

    def _get(self, base: str, path: str, params: dict | None = None) -> dict:
        r = self.session.get(f"{base}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # ── Broker ──────────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        return bool(self._get(self.base_url, "/v2/clock").get("is_open"))

    def snapshot(self, symbols: List[str]) -> MarketSnapshot:
        bars = self._get(DATA_URL, "/v2/stocks/bars", {
            "symbols": ",".join(symbols),
            "timeframe": "1Hour",
            "limit": 24,
            "feed": "iex",
        }).get("bars", {})

        symbol_data = []
        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if not sym_bars:
                continue
            candles = [
                Candle(open_time=b["t"], open=b["o"], high=b["h"],
                       low=b["l"], close=b["c"], volume=b["v"])
                for b in sym_bars
            ]
            first, last = candles[0], candles[-1]
            change = (last.close - first.open) / first.open * 100 if first.open else None
            symbol_data.append(SymbolData(
                symbol=sym, last_price=last.close,
                change_24h_pct=change, candles=candles,
            ))

        account = self._get(self.base_url, "/v2/account")
        raw_positions = self._get(self.base_url, "/v2/positions")
        positions = [
            Position(
                symbol=p["symbol"],
                qty=float(p["qty"]),
                avg_price=float(p["avg_entry_price"]),
                market_value=float(p["market_value"]),
                unrealized_pnl=float(p["unrealized_pl"]),
            )
            for p in raw_positions
        ]
        return MarketSnapshot(
            market="stocks",
            timestamp=datetime.now(timezone.utc).isoformat(),
            equity_usd=float(account["equity"]),
            cash_usd=float(account["cash"]),
            positions=positions,
            symbols=symbol_data,
        )

    def execute(self, order) -> ExecutedOrder:
        r = self.session.post(f"{self.base_url}/v2/orders", json={
            "symbol": order.symbol,
            "side": order.side,
            "type": "market",
            "time_in_force": "day",
            "notional": round(order.notional_usd, 2),
        }, timeout=15)
        r.raise_for_status()
        return ExecutedOrder(order.symbol, order.side, order.notional_usd, r.json()["id"])
