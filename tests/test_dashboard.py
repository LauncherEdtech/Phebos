import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Dashboard apontando para um banco temporário populado."""
    monkeypatch.setenv("PHEBOS_DATA_DIR", str(tmp_path))
    import phebos.config, phebos.journal, phebos.dashboard
    importlib.reload(phebos.config)
    importlib.reload(phebos.journal)
    importlib.reload(phebos.dashboard)
    from phebos.journal import Journal

    j = Journal()
    j.log_equity("demo", "crypto", 1000, 500)
    j.log_equity("demo", "stocks", 2000, 900)
    j.log_equity("demo", "crypto", 1050, 500)
    j.log_equity("demo", "stocks", 2050, 900)
    j.log_prices("demo", "crypto", {"BTCUSDT": 100.0})
    j.log_prices("demo", "crypto", {"BTCUSDT": 104.0})
    j.log_research("demo", "crypto", "briefing X")
    j.log_decision("demo", "crypto", "leitura do mercado", 1)
    j.log_trade("demo", "crypto", "BTCUSDT", "buy", 45, True, "ok", "tese A", "o1")
    j.record_buy("demo", "crypto", "BTCUSDT", 45, 100.0, "tese A", "high")
    j.log_trade("demo", "crypto", "ETHUSDT", "buy", 900, False, "limite", "tese B")
    j.record_buy("demo", "crypto", "SOLUSDT", 50, 10.0, "tese C", "low")
    j.record_sell("demo", "crypto", "SOLUSDT", 55, 11.0, "take_profit")
    j.save_lessons("demo", "lição registrada")
    return TestClient(phebos.dashboard.app)


def test_summary(client):
    s = client.get("/api/summary").json()
    # forward-fill: [3000, 3050, 3100] → último ponto 3100
    assert s["equity_now"] == 3100
    assert s["trades_executed"] == 1 and s["trades_vetoed"] == 1
    assert s["closed_trades"] == 1
    assert s["win_rate_pct"] == 100.0
    assert s["benchmark_return_pct"] == pytest.approx(4.0)
    assert s["demo_report"] is not None


def test_positions_endpoint(client):
    pos = client.get("/api/positions").json()
    assert len(pos) == 1 and pos[0]["symbol"] == "BTCUSDT"
    assert pos[0]["thesis"] == "tese A"


def test_realized_endpoint(client):
    r = client.get("/api/realized").json()
    assert r[0]["symbol"] == "SOLUSDT" and r[0]["reason"] == "take_profit"
    assert r[0]["pnl_pct"] == pytest.approx(10.0)


def test_history_unificado(client):
    h = client.get("/api/history").json()
    types = {item["type"] for item in h}
    assert {"leitura", "pensamento", "operacao", "resultado", "reflexao"} <= types
    # ordenado do mais novo para o mais antigo
    timestamps = [item["ts"] for item in h]
    assert timestamps == sorted(timestamps, reverse=True)
    veto = [i for i in h if i["type"] == "operacao" and "VETADA" in i["title"]]
    assert veto and "Veto" in veto[0]["body"]


def test_calibration_endpoint(client):
    cal = client.get("/api/calibration").json()
    assert cal["low"]["trades"] == 1


def test_lessons_endpoint(client):
    assert client.get("/api/lessons").json()["lessons_text"] == "lição registrada"


def test_pagina_html(client):
    html = client.get("/").text
    assert "Phebos" in html and "Histórico" in html
