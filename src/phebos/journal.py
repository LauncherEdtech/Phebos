"""Journal em SQLite: decisões, trades, briefings, patrimônio, posições e P&L.

Mantém o livro de posições (contabilidade por preço médio), o P&L realizado
de cada saída, os eventos de notícia já operados (dedupe) e o histórico de
preços para o benchmark buy-and-hold.
"""

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
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    last_price REAL NOT NULL,
    peak_price REAL NOT NULL,
    thesis TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(mode, market, symbol)
);
CREATE TABLE IF NOT EXISTS realized (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl_usd REAL NOT NULL,
    pnl_pct REAL NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events_acted (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    event_key TEXT NOT NULL,
    rationale TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    lessons_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calendar_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
"""

# Migrações de colunas para bancos criados em versões anteriores
_MIGRATIONS = [
    "ALTER TABLE positions ADD COLUMN confidence TEXT NOT NULL DEFAULT 'medium'",
    "ALTER TABLE realized ADD COLUMN thesis TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE realized ADD COLUMN confidence TEXT NOT NULL DEFAULT 'medium'",
]

# Quantidade residual abaixo disso (em US$) é tratada como poeira e fecha a posição
_DUST_USD = 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.executescript(_SCHEMA)
        for migration in _MIGRATIONS:
            try:
                self.conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # coluna já existe
        self.conn.commit()

    # ── registros básicos ───────────────────────────────────────────
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

    def log_prices(self, mode: str, market: str, prices: dict[str, float]) -> None:
        ts = _now()
        self.conn.executemany(
            "INSERT INTO prices (ts, mode, market, symbol, price) VALUES (?,?,?,?,?)",
            [(ts, mode, market, sym, p) for sym, p in prices.items()],
        )
        self.conn.commit()

    # ── livro de posições (contabilidade por preço médio) ───────────
    def record_buy(self, mode: str, market: str, symbol: str, notional_usd: float,
                   price: float, thesis: str, confidence: str = "medium") -> None:
        """Compra: aumenta a posição e recalcula o preço médio."""
        qty = notional_usd / price
        row = self.conn.execute(
            "SELECT qty, avg_price, peak_price FROM positions WHERE mode=? AND market=? AND symbol=?",
            (mode, market, symbol),
        ).fetchone()
        ts = _now()
        if row is None:
            self.conn.execute(
                "INSERT INTO positions (mode, market, symbol, qty, avg_price, last_price,"
                " peak_price, thesis, confidence, opened_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (mode, market, symbol, qty, price, price, price, thesis, confidence, ts, ts),
            )
        else:
            old_qty, old_avg, peak = row
            new_qty = old_qty + qty
            new_avg = (old_qty * old_avg + notional_usd) / new_qty
            self.conn.execute(
                "UPDATE positions SET qty=?, avg_price=?, last_price=?, peak_price=?,"
                " thesis=?, confidence=?, updated_at=? WHERE mode=? AND market=? AND symbol=?",
                (new_qty, new_avg, price, max(peak, price), thesis, confidence, ts,
                 mode, market, symbol),
            )
        self.conn.commit()

    def record_sell(self, mode: str, market: str, symbol: str, notional_usd: float,
                    price: float, reason: str) -> tuple[float, float]:
        """Venda: reduz/fecha a posição e realiza o P&L. Retorna (pnl_usd, pnl_pct)."""
        row = self.conn.execute(
            "SELECT qty, avg_price, thesis, confidence FROM positions"
            " WHERE mode=? AND market=? AND symbol=?",
            (mode, market, symbol),
        ).fetchone()
        if row is None:
            return 0.0, 0.0  # venda sem posição registrada (ex.: saldo pré-existente)
        qty, avg_price, thesis, confidence = row
        sell_qty = min(qty, notional_usd / price)
        pnl_usd = sell_qty * (price - avg_price)
        pnl_pct = (price - avg_price) / avg_price * 100 if avg_price else 0.0

        self.conn.execute(
            "INSERT INTO realized (ts, mode, market, symbol, qty, avg_price, exit_price,"
            " pnl_usd, pnl_pct, reason, thesis, confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_now(), mode, market, symbol, sell_qty, avg_price, price, pnl_usd, pnl_pct,
             reason, thesis, confidence),
        )
        remaining = qty - sell_qty
        if remaining * price < _DUST_USD:
            self.conn.execute(
                "DELETE FROM positions WHERE mode=? AND market=? AND symbol=?",
                (mode, market, symbol),
            )
        else:
            self.conn.execute(
                "UPDATE positions SET qty=?, last_price=?, updated_at=?"
                " WHERE mode=? AND market=? AND symbol=?",
                (remaining, price, _now(), mode, market, symbol),
            )
        self.conn.commit()
        return pnl_usd, pnl_pct

    def update_position_marks(self, mode: str, market: str, prices: dict[str, float]) -> None:
        """Atualiza last_price e peak_price (para trailing stop) das posições abertas."""
        for symbol, price in prices.items():
            self.conn.execute(
                "UPDATE positions SET last_price=?, peak_price=MAX(peak_price, ?), updated_at=?"
                " WHERE mode=? AND market=? AND symbol=?",
                (price, price, _now(), mode, market, symbol),
            )
        self.conn.commit()

    def get_open_positions(self, mode: str, market: str | None = None) -> list[dict]:
        query = ("SELECT market, symbol, qty, avg_price, last_price, peak_price, thesis,"
                 " opened_at FROM positions WHERE mode=?")
        params: list = [mode]
        if market:
            query += " AND market=?"
            params.append(market)
        rows = self.conn.execute(query, params).fetchall()
        positions = []
        for market_, symbol, qty, avg, last, peak, thesis, opened_at in rows:
            positions.append({
                "market": market_, "symbol": symbol, "qty": qty,
                "avg_price": avg, "last_price": last, "peak_price": peak,
                "thesis": thesis, "opened_at": opened_at,
                "notional_usd": qty * last,
                "pnl_pct": (last - avg) / avg * 100 if avg else 0.0,
            })
        return positions

    # ── eventos já operados (dedupe de notícias) ────────────────────
    def record_event(self, mode: str, market: str, symbol: str, side: str,
                     event_key: str, rationale: str) -> None:
        self.conn.execute(
            "INSERT INTO events_acted (ts, mode, market, symbol, side, event_key, rationale)"
            " VALUES (?,?,?,?,?,?,?)",
            (_now(), mode, market, symbol, side, event_key, rationale),
        )
        self.conn.commit()

    def recent_events(self, mode: str, days: int) -> list[dict]:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
        rows = self.conn.execute(
            "SELECT ts, market, symbol, side, event_key, rationale FROM events_acted"
            " WHERE mode=? AND ts >= ? ORDER BY ts DESC",
            (mode, cutoff_iso),
        ).fetchall()
        return [{"ts": r[0], "market": r[1], "symbol": r[2], "side": r[3],
                 "event_key": r[4], "rationale": r[5]} for r in rows]

    # ── memória para o analista ─────────────────────────────────────
    def recent_decisions(self, mode: str, market: str, limit: int = 5) -> list[dict]:
        rows = self.conn.execute(
            "SELECT ts, market_view, orders_proposed FROM decisions"
            " WHERE mode=? AND market=? ORDER BY ts DESC LIMIT ?",
            (mode, market, limit),
        ).fetchall()
        return [{"ts": r[0], "market_view": r[1], "orders_proposed": r[2]} for r in rows]

    # ── métricas e séries ───────────────────────────────────────────
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

    def realized_stats(self, mode: str) -> dict:
        """Métricas profissionais sobre as saídas realizadas."""
        rows = self.conn.execute(
            "SELECT pnl_usd FROM realized WHERE mode=?", (mode,)
        ).fetchall()
        pnls = [r[0] for r in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        gross_win, gross_loss = sum(wins), abs(sum(losses))
        return {
            "closed_trades": len(pnls),
            "realized_pnl_usd": sum(pnls),
            "win_rate_pct": len(wins) / len(pnls) * 100 if pnls else None,
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0
                             else (None if not wins else float("inf")),
            "avg_win_usd": gross_win / len(wins) if wins else 0.0,
            "avg_loss_usd": -gross_loss / len(losses) if losses else 0.0,
        }

    def realized_list(self, mode: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT ts, market, symbol, qty, avg_price, exit_price, pnl_usd, pnl_pct, reason,"
            " thesis, confidence FROM realized WHERE mode=? ORDER BY ts DESC LIMIT ?",
            (mode, limit),
        ).fetchall()
        return [{"ts": r[0], "market": r[1], "symbol": r[2], "qty": r[3], "avg_price": r[4],
                 "exit_price": r[5], "pnl_usd": r[6], "pnl_pct": r[7], "reason": r[8],
                 "thesis": r[9], "confidence": r[10]} for r in rows]

    # ── calibração de confiança (diferencial vs bots tradicionais) ──
    def confidence_calibration(self, mode: str) -> dict:
        """Taxa de acerto por nível de convicção declarado pela IA.

        Alimenta o prompt: se as ordens 'high' acertam menos que as 'medium',
        a IA fica sabendo — e o operador também.
        """
        rows = self.conn.execute(
            "SELECT confidence, COUNT(*), SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END),"
            " AVG(pnl_pct) FROM realized WHERE mode=? GROUP BY confidence",
            (mode,),
        ).fetchall()
        return {
            conf: {
                "trades": n,
                "win_rate_pct": wins / n * 100 if n else None,
                "avg_pnl_pct": round(avg_pnl, 2) if avg_pnl is not None else None,
            }
            for conf, n, wins, avg_pnl in rows
        }

    # ── lições aprendidas (auto-reflexão) ───────────────────────────
    def save_lessons(self, mode: str, lessons_text: str) -> None:
        self.conn.execute(
            "INSERT INTO lessons (ts, mode, lessons_text) VALUES (?,?,?)",
            (_now(), mode, lessons_text),
        )
        self.conn.commit()

    def latest_lessons(self, mode: str) -> dict | None:
        row = self.conn.execute(
            "SELECT ts, lessons_text FROM lessons WHERE mode=? ORDER BY ts DESC LIMIT 1",
            (mode,),
        ).fetchone()
        return {"ts": row[0], "lessons_text": row[1]} if row else None

    def closed_trades_since(self, mode: str, since_iso: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT ts, market, symbol, pnl_usd, pnl_pct, reason, thesis, confidence"
            " FROM realized WHERE mode=? AND ts >= ? ORDER BY ts",
            (mode, since_iso),
        ).fetchall()
        return [{"ts": r[0], "market": r[1], "symbol": r[2], "pnl_usd": r[3], "pnl_pct": r[4],
                 "reason": r[5], "thesis": r[6], "confidence": r[7]} for r in rows]

    # ── logs do agente (exibidos no dashboard) ──────────────────────
    def write_log(self, level: str, message: str) -> None:
        self.conn.execute(
            "INSERT INTO logs (ts, level, message) VALUES (?,?,?)",
            (_now(), level, message),
        )
        self.conn.commit()

    def get_logs(self, limit: int = 300, level: str | None = None) -> list[dict]:
        if level:
            rows = self.conn.execute(
                "SELECT ts, level, message FROM logs WHERE level=? ORDER BY id DESC LIMIT ?",
                (level, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT ts, level, message FROM logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"ts": r[0], "level": r[1], "message": r[2]} for r in rows]

    def prune_logs(self, keep: int = 5000) -> None:
        """Mantém só as últimas N linhas para o banco não crescer sem limite."""
        self.conn.execute(
            "DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT ?)",
            (keep,),
        )
        self.conn.commit()

    # ── calendário econômico (cache diário) ─────────────────────────
    def get_calendar(self, date: str) -> str | None:
        row = self.conn.execute(
            "SELECT text FROM calendar_cache WHERE date=?", (date,)
        ).fetchone()
        return row[0] if row else None

    def save_calendar(self, date: str, text: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO calendar_cache (date, text) VALUES (?,?)", (date, text)
        )
        self.conn.commit()

    def losing_streak(self, mode: str) -> int:
        """Nº de saídas com prejuízo consecutivas, da mais recente para trás.

        Alimenta o circuit breaker anti-tilt: sequência de perdas → sizing reduzido.
        """
        rows = self.conn.execute(
            "SELECT pnl_usd FROM realized WHERE mode=? ORDER BY ts DESC, id DESC", (mode,)
        ).fetchall()
        streak = 0
        for (pnl,) in rows:
            if pnl < 0:
                streak += 1
            else:
                break
        return streak

    def benchmark_return_pct(self, mode: str) -> float | None:
        """Retorno buy-and-hold: média (peso igual) da variação de cada símbolo
        entre o primeiro e o último preço registrados no período."""
        rows = self.conn.execute(
            "SELECT market, symbol, ts, price FROM prices WHERE mode=? ORDER BY ts", (mode,)
        ).fetchall()
        first: dict[tuple, float] = {}
        last: dict[tuple, float] = {}
        for market, symbol, _, price in rows:
            key = (market, symbol)
            first.setdefault(key, price)
            last[key] = price
        returns = [
            (last[k] - first[k]) / first[k] * 100
            for k in first if first[k] > 0
        ]
        return sum(returns) / len(returns) if returns else None
