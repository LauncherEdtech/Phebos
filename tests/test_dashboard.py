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


def test_logs_endpoint(client, tmp_path):
    import phebos.journal
    j = phebos.journal.Journal()
    j.write_log("INFO", "ciclo ok")
    j.write_log("ERROR", "deu ruim")
    logs = client.get("/api/logs").json()
    assert logs[0]["message"] == "deu ruim"
    only_err = client.get("/api/logs?level=ERROR").json()
    assert len(only_err) == 1 and only_err[0]["level"] == "ERROR"


def test_keys_endpoints(client, monkeypatch):
    # status inicial mascarado
    st = client.get("/api/keys/status").json()
    assert "GEMINI_API_KEY" in st
    # salvar
    r = client.post("/api/keys", json={"GEMINI_API_KEY": "AIzaTeste12345678"}).json()
    assert r["saved"] == ["GEMINI_API_KEY"]
    assert r["status"]["GEMINI_API_KEY"]["set"] is True
    assert "Teste1234" not in r["status"]["GEMINI_API_KEY"]["preview"]
    # testar conexões (mocka os testadores para não bater na rede)
    import phebos.keys as keys_mod
    monkeypatch.setattr(keys_mod, "test_gemini", lambda: {"ok": True, "detail": "ok"})
    monkeypatch.setattr(keys_mod, "test_binance", lambda: {"ok": None, "detail": "sem chave"})
    monkeypatch.setattr(keys_mod, "test_alpaca", lambda: {"ok": None, "detail": "sem chave"})
    monkeypatch.setattr(keys_mod, "test_telegram", lambda: {"ok": False, "detail": "token inválido"})
    results = client.post("/api/keys/test").json()
    assert results["gemini"]["ok"] is True and results["telegram"]["ok"] is False


def test_runtime_endpoints(client):
    # valor inicial (default do config de teste)
    r = client.get("/api/runtime").json()
    assert "interval_minutes" in r and r["interval_minutes"] >= 1
    # salvar novo
    saved = client.post("/api/runtime", json={"interval_minutes": 25}).json()
    assert saved["interval_minutes"] == 25
    assert client.get("/api/runtime").json()["interval_minutes"] == 25
    # mínimo aplicado
    assert client.post("/api/runtime", json={"interval_minutes": 0}).json()["interval_minutes"] == 1
    # inválido
    assert "error" in client.post("/api/runtime", json={}).json()


def test_run_now_endpoint(client):
    assert client.post("/api/run-now").json()["requested"] is True
    # o pedido fica registrado para o agente consumir
    import phebos.config
    assert phebos.config.consume_run_now() is True
