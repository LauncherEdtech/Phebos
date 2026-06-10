"""Journal em SQLite: decisões da IA, trades executados e curva de patrimônio."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    market_view TEXT NOT NULL,
    orders_proposed INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    notional_usd REAL NOT NULL,
    broker_order_id TEXT,
    approved INTEGER NOT NULL,
    reason TEXT NOT NULL,
    rationale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    briefing TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    equity_usd REAL NOT NULL,
    cash_usd REAL NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.executescript(_SCHEMA)

    def log_decision(self, mode: str, market: str, market_view: str, orders_proposed: int) -> None:
        self.conn.execute(
            "INSERT INTO decisions (ts, mode, market, market_view, orders_proposed) VALUES (?,?,?,?,?)",
            (_now(), mode, market, market_view, orders_proposed),
        )
        self.conn.commit()

    def log_research(self, mode: str, market: str, briefing: str) -> None:
        self.conn.execute(
            "INSERT INTO research (ts, mode, market, briefing) VALUES (?,?,?,?)",
            (_now(), mode, market, briefing),
        )
        self.conn.commit()

    def log_trade(self, mode: str, market: str, symbol: str, side: str, notional_usd: float,
                  approved: bool, reason: str, rationale: str, broker_order_id: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO trades (ts, mode, market, symbol, side, notional_usd, broker_order_id,"
            " approved, reason, rationale) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_now(), mode, market, symbol, side, notional_usd, broker_order_id,
             int(approved), reason, rationale),
        )
        self.conn.commit()

    def log_equity(self, mode: str, market: str, equity_usd: float, cash_usd: float) -> None:
        self.conn.execute(
            "INSERT INTO equity (ts, mode, market, equity_usd, cash_usd) VALUES (?,?,?,?,?)",
            (_now(), mode, market, equity_usd, cash_usd),
        )
        self.conn.commit()

    def daily_pnl_pct(self, mode: str, market: str) -> float:
        """Variação % do patrimônio desde o primeiro registro de hoje (UTC)."""
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self.conn.execute(
            "SELECT equity_usd FROM equity WHERE mode=? AND market=? AND ts >= ? ORDER BY ts",
            (mode, market, today),
        ).fetchall()
        if len(rows) < 2 or rows[0][0] == 0:
            return 0.0
        return (rows[-1][0] - rows[0][0]) / rows[0][0] * 100

    def equity_series(self, mode: str):
        """Patrimônio TOTAL ao longo do tempo, somando os mercados.

        Cada mercado registra em timestamps próprios; usamos forward-fill
        (último valor conhecido de cada mercado) e só começamos a série
        quando todos os mercados já registraram ao menos uma vez — senão o
        total daria um salto artificial na primeira aparição de um mercado.
        """
        rows = self.conn.execute(
            "SELECT ts, market, equity_usd FROM equity WHERE mode=? ORDER BY ts",
            (mode,),
        ).fetchall()
        markets = {market for _, market, _ in rows}
        last: dict[str, float] = {}
        series = []
        for ts, market, eq in rows:
            last[market] = eq
            if len(last) == len(markets):
                series.append((ts, sum(last.values())))
        return series

    def executed_trades(self, mode: str):
        return self.conn.execute(
            "SELECT ts, market, symbol, side, notional_usd FROM trades WHERE mode=? AND approved=1 ORDER BY ts",
            (mode,),
        ).fetchall()
