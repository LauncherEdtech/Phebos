import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phebos.journal import Journal  # noqa: E402
from phebos.schemas import Candle, MarketSnapshot, Position, SymbolData  # noqa: E402


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / "test.db")


def make_candles(prices: list[float], spread: float = 1.0, volume: float = 1000.0):
    return [
        Candle(open_time=f"2026-06-01T{i % 24:02d}:00:00+00:00",
               open=p, high=p + spread, low=p - spread, close=p, volume=volume)
        for i, p in enumerate(prices)
    ]


def make_snapshot(symbol="BTCUSDT", price=100.0, prices_1h=None, prices_4h=None,
                  prices_1d=None, equity=1000.0, cash=800.0, positions=None,
                  market="crypto"):
    return MarketSnapshot(
        market=market, timestamp="2026-06-10T12:00:00+00:00",
        equity_usd=equity, cash_usd=cash, positions=positions or [],
        symbols=[SymbolData(
            symbol=symbol, last_price=price, change_24h_pct=1.0,
            candles=make_candles(prices_1h or [price] * 24),
            candles_4h=make_candles(prices_4h) if prices_4h else [],
            candles_1d=make_candles(prices_1d) if prices_1d else [],
        )],
    )


@pytest.fixture
def snapshot():
    return make_snapshot()


def make_position(symbol="BTCUSDT", qty=0.5, avg=100.0, last=100.0, peak=100.0,
                  thesis="tese de teste", market="crypto"):
    return {"market": market, "symbol": symbol, "qty": qty, "avg_price": avg,
            "last_price": last, "peak_price": peak, "thesis": thesis,
            "opened_at": "2026-06-09T00:00:00+00:00",
            "notional_usd": qty * last,
            "pnl_pct": (last - avg) / avg * 100 if avg else 0.0}
