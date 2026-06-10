"""Dashboard web: relatórios financeiros, operações, decisões e briefings.

    python -m phebos.main dashboard          # http://localhost:8000

Lê o mesmo SQLite que o agente escreve — pode rodar em paralelo.
"""

import sqlite3
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import (
    DB_PATH, find_config, get_runtime_interval, request_run_now, set_runtime_interval,
)
from .evaluation import evaluate_demo
from .journal import Journal

app = FastAPI(title="Phebos Dashboard")

_WEB = Path(__file__).parent / "web"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _raw_config() -> dict:
    try:
        return yaml.safe_load(find_config().read_text()) or {}
    except Exception:
        return {}


def _mode() -> str:
    return _raw_config().get("mode", "demo")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_WEB / "index.html").read_text(encoding="utf-8")


@app.get("/api/summary")
def summary(mode: str | None = None):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return {"mode": mode, "empty": True}

    journal = Journal(DB_PATH)
    series = journal.equity_series(mode)
    trades = journal.conn.execute(
        "SELECT approved, COUNT(*) FROM trades WHERE mode=? GROUP BY approved", (mode,)
    ).fetchall()
    counts = {row[0]: row[1] for row in trades}

    from .config import DemoConfig
    report = evaluate_demo(journal, DemoConfig(**_raw_config().get("demo", {})))

    values = [v for _, v in series if v]
    pf = report.profit_factor if report else None
    return {
        "mode": mode,
        "empty": not series,
        "equity_now": values[-1] if values else 0,
        "equity_start": values[0] if values else 0,
        "return_pct": report.return_pct if report else 0,
        "max_drawdown_pct": report.max_drawdown_pct if report else 0,
        "days_running": report.days_running if report else 0,
        "trades_executed": counts.get(1, 0),
        "trades_vetoed": counts.get(0, 0),
        "last_update": series[-1][0] if series else None,
        # métricas profissionais
        "closed_trades": report.closed_trades if report else 0,
        "realized_pnl_usd": report.realized_pnl_usd if report else 0,
        "win_rate_pct": report.win_rate_pct if report else None,
        "profit_factor": None if pf == float("inf") else pf,
        "benchmark_return_pct": report.benchmark_return_pct if report else None,
        "alpha_pct": report.alpha_pct if report else None,
        "demo_report": {
            "approved": report.approved,
            "criteria": [{"label": label, "ok": ok} for label, ok in report.criteria],
        } if report else None,
    }


@app.get("/api/positions")
def positions(mode: str | None = None):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    return Journal(DB_PATH).get_open_positions(mode)


@app.get("/api/realized")
def realized(mode: str | None = None, limit: int = 100):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    return Journal(DB_PATH).realized_list(mode, limit)


@app.get("/api/equity")
def equity(mode: str | None = None):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    rows = _conn().execute(
        "SELECT ts, market, equity_usd FROM equity WHERE mode=? ORDER BY ts", (mode,)
    ).fetchall()
    return [{"ts": r["ts"], "market": r["market"], "equity_usd": r["equity_usd"]} for r in rows]


@app.get("/api/trades")
def trades(mode: str | None = None, limit: int = 200):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    rows = _conn().execute(
        "SELECT ts, market, symbol, side, notional_usd, approved, reason, rationale,"
        " broker_order_id FROM trades WHERE mode=? ORDER BY ts DESC LIMIT ?",
        (mode, limit),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/decisions")
def decisions(mode: str | None = None, limit: int = 50):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    rows = _conn().execute(
        "SELECT ts, market, market_view, orders_proposed FROM decisions"
        " WHERE mode=? ORDER BY ts DESC LIMIT ?",
        (mode, limit),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/history")
def history(mode: str | None = None, limit: int = 300):
    """Linha do tempo unificada do bot: leituras (briefings), pensamentos
    (decisões), operações, resultados (P&L) e reflexões (lições)."""
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    conn = _conn()
    items: list[dict] = []

    for r in conn.execute(
            "SELECT ts, market, briefing FROM research WHERE mode=? ORDER BY ts DESC LIMIT ?",
            (mode, limit)):
        items.append({"ts": r["ts"], "type": "leitura", "market": r["market"],
                      "title": "Leitura de mercado (pesquisador)", "body": r["briefing"]})

    for r in conn.execute(
            "SELECT ts, market, market_view, orders_proposed FROM decisions"
            " WHERE mode=? ORDER BY ts DESC LIMIT ?", (mode, limit)):
        items.append({"ts": r["ts"], "type": "pensamento", "market": r["market"],
                      "title": f"Pensamento — {r['orders_proposed']} ordem(ns) proposta(s)",
                      "body": r["market_view"]})

    for r in conn.execute(
            "SELECT ts, market, symbol, side, notional_usd, approved, reason, rationale"
            " FROM trades WHERE mode=? ORDER BY ts DESC LIMIT ?", (mode, limit)):
        verb = "Compra" if r["side"] == "buy" else "Venda"
        status = "executada" if r["approved"] else "VETADA"
        items.append({"ts": r["ts"], "type": "operacao", "market": r["market"],
                      "title": f"{verb} {r['symbol']} ${r['notional_usd']:.2f} — {status}",
                      "body": r["rationale"] if r["approved"]
                              else f"Veto: {r['reason']} | Justificativa da IA: {r['rationale']}",
                      "approved": bool(r["approved"]), "side": r["side"]})

    for r in conn.execute(
            "SELECT ts, market, symbol, pnl_usd, pnl_pct, reason FROM realized"
            " WHERE mode=? ORDER BY ts DESC LIMIT ?", (mode, limit)):
        items.append({"ts": r["ts"], "type": "resultado", "market": r["market"],
                      "title": f"Posição encerrada {r['symbol']}: "
                               f"{'+' if r['pnl_usd'] >= 0 else ''}{r['pnl_usd']:.2f} USD "
                               f"({r['pnl_pct']:+.2f}%)",
                      "body": f"Motivo da saída: {r['reason']}",
                      "pnl_usd": r["pnl_usd"]})

    for r in conn.execute(
            "SELECT ts, lessons_text FROM lessons WHERE mode=? ORDER BY ts DESC LIMIT 10",
            (mode,)):
        items.append({"ts": r["ts"], "type": "reflexao", "market": "geral",
                      "title": "Auto-reflexão — lições aprendidas", "body": r["lessons_text"]})

    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:limit]


@app.get("/api/lessons")
def lessons(mode: str | None = None):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return None
    return Journal(DB_PATH).latest_lessons(mode)


@app.get("/api/calibration")
def calibration(mode: str | None = None):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return {}
    return Journal(DB_PATH).confidence_calibration(mode)


@app.get("/api/runtime")
def runtime_get():
    """Intervalo atual do ciclo (min) — o que o agente está usando."""
    default = int(_raw_config().get("interval_minutes", 15))
    return {"interval_minutes": get_runtime_interval(default)}


@app.post("/api/runtime")
def runtime_set(payload: dict):
    """Define o intervalo do ciclo (mínimo 1 min). O agente aplica no próximo passo."""
    minutes = payload.get("interval_minutes")
    if minutes is None:
        return {"error": "interval_minutes é obrigatório"}
    try:
        saved = set_runtime_interval(int(minutes))
    except (ValueError, TypeError):
        return {"error": "interval_minutes inválido"}
    return {"interval_minutes": saved}


@app.post("/api/run-now")
def run_now():
    """Pede ao agente um ciclo imediato (sem esperar o intervalo)."""
    request_run_now()
    return {"requested": True}


@app.get("/api/keys/status")
def keys_status():
    """Quais chaves estão configuradas (apenas prévia mascarada — nunca o valor)."""
    from . import keys
    return keys.masked_status()


@app.post("/api/keys")
def keys_save(payload: dict):
    """Salva chaves não vazias em DATA_DIR/secrets.env (o agente recarrega no
    próximo ciclo). Nunca apaga uma chave existente — só sobrescreve."""
    from . import keys
    saved = keys.save_secrets(payload or {})
    return {"saved": saved, "status": keys.masked_status()}


@app.post("/api/keys/test")
def keys_test():
    """Testa as conexões com 1 chamada barata por serviço configurado."""
    from . import keys
    return keys.run_tests()


@app.get("/api/logs")
def logs(limit: int = 300, level: str | None = None):
    """Logs do agente (gravados pelo JournalLogHandler), mais novos primeiro."""
    if not DB_PATH.exists():
        return []
    return Journal(DB_PATH).get_logs(limit, level)


@app.get("/api/research")
def research(mode: str | None = None, limit: int = 20):
    mode = mode or _mode()
    if not DB_PATH.exists():
        return []
    rows = _conn().execute(
        "SELECT ts, market, briefing FROM research WHERE mode=? ORDER BY ts DESC LIMIT ?",
        (mode, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
