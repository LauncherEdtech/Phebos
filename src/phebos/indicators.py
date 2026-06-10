"""Indicadores técnicos multi-timeframe + detecção de regime de mercado."""

from typing import List, Optional

from .schemas import Candle, MarketSnapshot


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


def _atr_pct(candles: List[Candle], period: int = 14) -> Optional[float]:
    """ATR como % do preço — mede a volatilidade do ativo (para sizing)."""
    if len(candles) < period + 1:
        return None
    trs = []
    for prev, curr in zip(candles[-period - 1:-1], candles[-period:]):
        tr = max(curr.high - curr.low,
                 abs(curr.high - prev.close),
                 abs(curr.low - prev.close))
        trs.append(tr)
    atr = sum(trs) / period
    last_close = candles[-1].close
    return atr / last_close * 100 if last_close else None


def _trend(candles: List[Candle], sma_period: int = 20, slope_lookback: int = 5) -> Optional[dict]:
    """Tendência de um timeframe: preço vs SMA e inclinação da SMA."""
    closes = [c.close for c in candles]
    sma_now = _sma(closes, sma_period)
    sma_before = _sma(closes[:-slope_lookback], sma_period) if len(closes) > slope_lookback else None
    if sma_now is None:
        return None
    price = closes[-1]
    slope_pct = ((sma_now - sma_before) / sma_before * 100) if sma_before else None
    return {
        "price_vs_sma20_pct": round((price - sma_now) / sma_now * 100, 2),
        "sma20_slope_pct": round(slope_pct, 2) if slope_pct is not None else None,
        "direction": ("alta" if price > sma_now and (slope_pct or 0) >= 0
                      else "baixa" if price < sma_now and (slope_pct or 0) <= 0
                      else "lateral"),
    }


def _symbol_regime(sym) -> str:
    """Regime do ativo: prioriza 4h; cai para 1h se não houver dados."""
    trend = _trend(sym.candles_4h) or _trend(sym.candles)
    return trend["direction"] if trend else "lateral"


def compute_market_regime(snapshot: MarketSnapshot) -> str:
    """Regime do mercado: voto majoritário dos ativos (alta/baixa/lateral)."""
    votes = [_symbol_regime(s) for s in snapshot.symbols if s.candles or s.candles_4h]
    if not votes:
        return "lateral"
    up, down = votes.count("alta"), votes.count("baixa")
    if up > len(votes) / 2:
        return "alta"
    if down > len(votes) / 2:
        return "baixa"
    return "lateral"


def compute_indicators(snapshot: MarketSnapshot) -> dict:
    """Indicadores por símbolo (1h + 4h + 1d) e regime agregado do mercado."""
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
        rsi = _rsi(closes)
        entry = {
            "rsi14_1h": round(rsi, 1) if rsi is not None else None,
            "sma8_1h": round(sma8, 4) if sma8 else None,
            "sma20_1h": round(sma20, 4) if sma20 else None,
            "price_vs_sma20_1h_pct": round((price - sma20) / sma20 * 100, 2) if sma20 else None,
            "volume_trend_1h": round(vol_trend, 2) if vol_trend else None,  # >1 = volume crescendo
            "atr14_pct": None,
            "regime": _symbol_regime(sym),
        }
        atr = _atr_pct(sym.candles)
        if atr is not None:
            entry["atr14_pct"] = round(atr, 2)
        if sym.candles_4h:
            entry["tf_4h"] = _trend(sym.candles_4h)
        if sym.candles_1d:
            entry["tf_1d"] = _trend(sym.candles_1d)
        result[sym.symbol] = entry

    result["_market_regime"] = compute_market_regime(snapshot)
    return result


def atr_by_symbol(indicators: dict) -> dict[str, float]:
    """Extrai {símbolo: atr_pct} para o dimensionamento de posição."""
    return {sym: data["atr14_pct"]
            for sym, data in indicators.items()
            if isinstance(data, dict) and data.get("atr14_pct") is not None}
