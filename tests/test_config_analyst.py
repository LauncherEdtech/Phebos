import pytest

from phebos.analyst import Analyst
from phebos.config import LIVE_CONFIRMATION, load_settings
from conftest import make_position, make_snapshot

CONFIG_YAML = """
mode: {mode}
interval_minutes: 5
markets:
  crypto: {{enabled: true, symbols: [BTCUSDT]}}
  stocks: {{enabled: false, symbols: []}}
risk: {{max_pct_per_trade: 4, stop_loss_pct: 6}}
demo: {{min_days: 10, must_beat_benchmark: false}}
news:
  max_headlines_per_feed: 5
  rss_feeds: {{crypto: [http://x]}}
sentiment:
  enabled: false
  reddit_subs: {{crypto: [Bitcoin]}}
calendar: {{enabled: false}}
reflection: {{every_days: 3}}
analyst: {{model: gemini-2.5-flash, web_search: false}}
notifications: {{telegram: false}}
"""


def write_cfg(tmp_path, mode="demo"):
    p = tmp_path / "config.yaml"
    p.write_text(CONFIG_YAML.format(mode=mode))
    return p


def test_load_settings_completo(tmp_path):
    s = load_settings(write_cfg(tmp_path))
    assert s.mode == "demo" and s.interval_minutes == 5
    assert s.risk.max_pct_per_trade == 4 and s.risk.stop_loss_pct == 6
    assert s.risk.vol_target_atr_pct == 4.0  # default preservado
    assert s.demo.min_days == 10 and s.demo.must_beat_benchmark is False
    assert s.sentiment_enabled is False
    assert s.reddit_subs_for("crypto") == ["Bitcoin"]
    assert s.reddit_subs_for("stocks") == []
    assert s.calendar_enabled is False
    assert s.reflection_every_days == 3
    assert s.telegram_enabled is False


def test_modo_live_bloqueado_sem_confirmacao(tmp_path, monkeypatch):
    monkeypatch.delenv("PHEBOS_CONFIRM_LIVE", raising=False)
    with pytest.raises(RuntimeError, match="Modo LIVE bloqueado"):
        load_settings(write_cfg(tmp_path, mode="live"))


def test_modo_live_liberado_com_confirmacao(tmp_path, monkeypatch):
    monkeypatch.setenv("PHEBOS_CONFIRM_LIVE", LIVE_CONFIRMATION)
    assert load_settings(write_cfg(tmp_path, mode="live")).is_live


def test_modo_invalido(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(CONFIG_YAML.format(mode="turbo"))
    with pytest.raises(ValueError):
        load_settings(p)


def test_credenciais_ausentes_erro_claro(tmp_path, monkeypatch):
    for var in ("BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings(write_cfg(tmp_path))
    with pytest.raises(RuntimeError, match="BINANCE_TESTNET"):
        s.broker_credentials("crypto")


# ── analista: helpers de prompt (sem chamadas de API) ───────────────
def test_snapshot_for_prompt_poda_candles():
    snap = make_snapshot(prices_1h=[100.0] * 48, prices_4h=[100.0] * 30,
                         prices_1d=[100.0] * 30)
    data = Analyst._snapshot_for_prompt(snap)
    sym = data["symbols"][0]
    assert len(sym["candles"]) == 12
    assert "candles_4h" not in sym and "candles_1d" not in sym


def test_format_memory_completo():
    text = Analyst._format_memory(
        [make_position(thesis="comprado por noticia X")],
        [{"ts": "2026-06-10T10:00", "market_view": "alta", "orders_proposed": 1}],
        [{"ts": "2026-06-09T10:00", "event_key": "evento-x", "side": "buy",
          "symbol": "BTCUSDT"}],
    )
    assert "comprado por noticia X" in text
    assert "evento-x" in text
    assert "alta" in text


def test_format_memory_vazio():
    text = Analyst._format_memory([], [], [])
    assert text.count("(nenhum") >= 3
