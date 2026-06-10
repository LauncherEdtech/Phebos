"""Indicadores técnicos calculados a partir dos candles do snapshot."""

from typing import List, Optional

from .schemas import MarketSnapshot


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, curr in zip(closes[-period - 1:-1], closes[-period:]):
        delta = curr - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def compute_indicators(snapshot: MarketSnapshot) -> dict:
    """RSI(14), SMA(8/20), posição do preço vs. médias e tendência de volume, por símbolo."""
    result: dict[str, dict] = {}
    for sym in snapshot.symbols:
        closes = [c.close for c in sym.candles]
        volumes = [c.volume for c in sym.candles]
        if not closes:
            continue
        price = sym.last_price
        sma8, sma20 = _sma(closes, 8), _sma(closes, 20)
        half = len(volumes) // 2
        vol_trend = None
        if half >= 2 and sum(volumes[:half]) > 0:
            vol_trend = (sum(volumes[half:]) / (len(volumes) - half)) / (sum(volumes[:half]) / half)
        result[sym.symbol] = {
            "rsi14": round(_rsi(closes), 1) if _rsi(closes) is not None else None,
            "sma8": round(sma8, 4) if sma8 else None,
            "sma20": round(sma20, 4) if sma20 else None,
            "price_vs_sma20_pct": round((price - sma20) / sma20 * 100, 2) if sma20 else None,
            "volume_trend": round(vol_trend, 2) if vol_trend else None,  # >1 = volume crescendo
        }
    return result
