"""Orquestra as camadas de inteligência: calendário econômico e auto-reflexão."""

import logging
from datetime import datetime, timedelta, timezone

from .analyst import Analyst
from .journal import Journal

log = logging.getLogger("phebos")


def get_daily_calendar(journal: Journal, analyst: Analyst, all_symbols: list[str],
                       enabled: bool = True) -> str:
    """Calendário econômico dos próximos dias — 1 busca por dia, cacheada."""
    if not enabled:
        return ""
    today = datetime.now(timezone.utc).date().isoformat()
    cached = journal.get_calendar(today)
    if cached is not None:
        return cached
    try:
        text = analyst.calendar_briefing(all_symbols)
    except Exception as exc:
        log.warning("calendário econômico indisponível: %s", exc)
        return ""
    journal.save_calendar(today, text)
    log.info("calendário econômico atualizado para %s", today)
    return text


def maybe_reflect(journal: Journal, analyst: Analyst, mode: str,
                  every_days: int = 7, min_trades: int = 3) -> str:
    """Auto-reflexão periódica: o agente revisa os próprios trades fechados
    e gera lições que entram no prompt dos próximos ciclos.

    Retorna o texto de lições mais recente (novo ou anterior).
    """
    latest = journal.latest_lessons(mode)
    now = datetime.now(timezone.utc)
    if latest:
        last_ts = datetime.fromisoformat(latest["ts"])
        due = now - last_ts >= timedelta(days=every_days)
        since = latest["ts"]
    else:
        due = True
        since = (now - timedelta(days=every_days)).isoformat()

    if not due:
        return latest["lessons_text"] if latest else ""

    closed = journal.closed_trades_since(mode, since)
    if len(closed) < min_trades:
        return latest["lessons_text"] if latest else ""

    try:
        lessons = analyst.reflect(closed, journal.confidence_calibration(mode))
    except Exception as exc:
        log.warning("auto-reflexão falhou: %s", exc)
        return latest["lessons_text"] if latest else ""
    journal.save_lessons(mode, lessons)
    log.info("auto-reflexão concluída: %d trades revisados, lições atualizadas", len(closed))
    return lessons
