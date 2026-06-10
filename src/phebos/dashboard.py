"""Dashboard web: relatórios financeiros, operações, decisões e briefings.

    python -m phebos.main dashboard          # http://localhost:8000

Lê o mesmo SQLite que o agente escreve — pode rodar em paralelo.
"""

import sqlite3
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import DB_PATH, ROOT
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
        return yaml.safe_load((ROOT / "config.yaml").read_text()) or {}
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
        "demo_report": {
            "approved": report.approved,
            "criteria": [{"label": label, "ok": ok} for label, ok in report.criteria],
        } if report else None,
    }


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
