"""Persistência em SQLite: cobranças e pagamentos recebidos."""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import Charge, ChargeStatus, PaymentEvent, utcnow_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txid TEXT NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    copy_paste_code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendente',
    provider TEXT NOT NULL DEFAULT 'fake',
    created_at TEXT NOT NULL,
    paid_at TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txid TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    provider TEXT NOT NULL,
    payer_name TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL,
    charge_id INTEGER,
    received_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);
-- Idempotência: o mesmo txid confirmado duas vezes pelo mesmo PSP é um
-- webhook repetido, não um pagamento novo.
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_txid_confirmed
    ON payments (provider, txid) WHERE outcome = 'confirmado';
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount_cents INTEGER NOT NULL,
    pix_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    transfer_ref TEXT NOT NULL DEFAULT '',
    requested_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── cobranças ───────────────────────────────────────────────────
    def save_charge(self, charge: Charge) -> Charge:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO charges (txid, amount_cents, description, copy_paste_code,"
                " status, provider, created_at, paid_at) VALUES (?,?,?,?,?,?,?,?)",
                (charge.txid, charge.amount_cents, charge.description,
                 charge.copy_paste_code, charge.status.value, charge.provider,
                 charge.created_at, charge.paid_at),
            )
            charge.id = cur.lastrowid
        return charge

    def get_charge_by_txid(self, txid: str) -> Optional[Charge]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM charges WHERE txid = ?", (txid,)).fetchone()
        return self._row_to_charge(row) if row else None

    def get_charge(self, charge_id: int) -> Optional[Charge]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM charges WHERE id = ?", (charge_id,)).fetchone()
        return self._row_to_charge(row) if row else None

    def pending_charges(self) -> List[Charge]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charges WHERE status = ? ORDER BY id",
                (ChargeStatus.PENDING.value,),
            ).fetchall()
        return [self._row_to_charge(r) for r in rows]

    def mark_paid(self, charge_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE charges SET status = ?, paid_at = ? WHERE id = ?",
                (ChargeStatus.PAID.value, utcnow_iso(), charge_id),
            )

    def mark_canceled(self, charge_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE charges SET status = ? WHERE id = ? AND status = ?",
                (ChargeStatus.CANCELED.value, charge_id, ChargeStatus.PENDING.value),
            )

    def paid_charges_since(self, iso_timestamp: str) -> List[Charge]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charges WHERE status = ? AND paid_at >= ? ORDER BY paid_at",
                (ChargeStatus.PAID.value, iso_timestamp),
            ).fetchall()
        return [self._row_to_charge(r) for r in rows]

    def recent_charges(self, limit: int = 50) -> List[Charge]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charges ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [self._row_to_charge(r) for r in rows]

    # ── pagamentos ──────────────────────────────────────────────────
    def record_payment(self, event: PaymentEvent, outcome: str,
                       charge_id: Optional[int], raw: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO payments (txid, amount_cents, provider, payer_name,"
                " outcome, charge_id, received_at, raw_json) VALUES (?,?,?,?,?,?,?,?)",
                (event.txid, event.amount_cents, event.provider, event.payer_name,
                 outcome, charge_id, event.received_at,
                 json.dumps(raw, ensure_ascii=False)),
            )

    def has_confirmed_payment(self, provider: str, txid: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM payments WHERE provider = ? AND txid = ? AND outcome = 'confirmado'",
                (provider, txid),
            ).fetchone()
        return row is not None

    def recent_payments(self, limit: int = 50) -> List[dict]:
        """Últimos pagamentos recebidos (para os painéis)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT p.txid, p.amount_cents, p.provider, p.payer_name,"
                " p.outcome, p.charge_id, p.received_at, c.description"
                " FROM payments p LEFT JOIN charges c ON c.id = p.charge_id"
                " ORDER BY p.id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── transferências (auditoria + limite diário) ──────────────────
    def record_transfer(self, amount_cents: int, pix_key: str, provider: str,
                        transfer_ref: str, requested_by: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO transfers (amount_cents, pix_key, provider,"
                " transfer_ref, requested_by, created_at) VALUES (?,?,?,?,?,?)",
                (amount_cents, pix_key, provider, transfer_ref, requested_by,
                 utcnow_iso()),
            )

    def transfers_total_since(self, iso_timestamp: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) AS total FROM transfers"
                " WHERE created_at >= ?", (iso_timestamp,),
            ).fetchone()
        return int(row["total"])

    @staticmethod
    def _row_to_charge(row: sqlite3.Row) -> Charge:
        return Charge(
            id=row["id"], txid=row["txid"], amount_cents=row["amount_cents"],
            description=row["description"], copy_paste_code=row["copy_paste_code"],
            status=ChargeStatus(row["status"]), provider=row["provider"],
            created_at=row["created_at"], paid_at=row["paid_at"],
        )
