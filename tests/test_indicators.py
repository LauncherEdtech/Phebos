from conftest import make_candles, make_snapshot

from phebos.indicators import (
    _atr_pct, _rsi, _sma, _trend, atr_by_symbol, compute_indicators,
    compute_market_regime,
)
from phebos.schemas import MarketSnapshot, SymbolData


def test_sma_basico():
    assert _sma([1, 2, 3, 4], 2) == 3.5
    assert _sma([1, 2], 5) is None


def test_rsi_alta_pura_eh_100():
    closes = list(range(1, 30))
    assert _rsi(closes) == 100.0


def test_rsi_queda_pura_eh_0():
    closes = list(range(30, 1, -1))
    assert _rsi(closes) == 0.0


def test_rsi_lateral_perto_de_50():
    closes = [100 + (1 if i % 2 == 0 else -1) for i in range(30)]
    rsi = _rsi(closes)
    assert 40 <= rsi <= 60


def test_rsi_dados_insuficientes():
    assert _rsi([1, 2, 3]) is None


def test_atr_pct():
    # candles com range fixo de 2 (high-low) em preço 100 → ATR ≈ 2%
    candles = make_candles([100.0] * 20, spread=1.0)
    atr = _atr_pct(candles)
    assert abs(atr - 2.0) < 0.01


def test_atr_dados_insuficientes():
    assert _atr_pct(make_candles([100.0] * 5)) is None


def test_trend_alta():
    candles = make_candles([100 + i for i in range(30)])
    t = _trend(candles)
    assert t["direction"] == "alta"
    assert t["price_vs_sma20_pct"] > 0


def test_trend_baixa():
    candles = make_candles([130 - i for i in range(30)])
    assert _trend(candles)["direction"] == "baixa"


def test_trend_dados_insuficientes():
    assert _trend(make_candles([100.0] * 5)) is None


def test_regime_alta_por_4h():
    snap = make_snapshot(prices_1h=[100.0] * 24, prices_4h=[100 + i for i in range(30)],
                         price=130.0)
    assert compute_market_regime(snap) == "alta"


def test_regime_fallback_1h():
    snap = make_snapshot(prices_1h=[130 - i for i in range(30)], price=100.0)
    assert compute_market_regime(snap) == "baixa"


def test_regime_sem_dados_eh_lateral():
    snap = MarketSnapshot(market="crypto", timestamp="t", equity_usd=1, cash_usd=1,
                          positions=[], symbols=[])
    assert compute_market_regime(snap) == "lateral"


def test_regime_voto_majoritario():
    sym_up = SymbolData(symbol="A", last_price=130,
                        candles=make_candles([100 + i for i in range(30)]))
    sym_down = SymbolData(symbol="B", last_price=100,
                          candles=make_candles([130 - i for i in range(30)]))
    snap = MarketSnapshot(market="crypto", timestamp="t", equity_usd=1, cash_usd=1,
                          positions=[], symbols=[sym_up, sym_down])
    assert compute_market_regime(snap) == "lateral"  # empate → lateral


def test_compute_indicators_completo():
    snap = make_snapshot(prices_1h=[100 + i * 0.5 for i in range(48)],
                         prices_4h=[90 + i for i in range(30)],
                         prices_1d=[80 + i * 2 for i in range(30)],
                         price=125.0)
    ind = compute_indicators(snap)
    btc = ind["BTCUSDT"]
    assert btc["rsi14_1h"] is not None
    assert btc["atr14_pct"] is not None
    assert btc["tf_4h"]["direction"] == "alta"
    assert btc["tf_1d"]["direction"] == "alta"
    assert btc["regime"] == "alta"
    assert ind["_market_regime"] == "alta"


def test_atr_by_symbol_ignora_chave_de_regime():
    snap = make_snapshot()
    ind = compute_indicators(snap)
    atr_map = atr_by_symbol(ind)
    assert "_market_regime" not in atr_map
    assert "BTCUSDT" in atr_map
