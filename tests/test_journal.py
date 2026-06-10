from phebos.journal import Journal


# ── contabilidade por preço médio ───────────────────────────────────
def test_compra_abre_posicao(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 50.0, "tese A", "high")
    pos = journal.get_open_positions("demo", "crypto")[0]
    assert pos["qty"] == 2.0 and pos["avg_price"] == 50.0 and pos["thesis"] == "tese A"


def test_segunda_compra_recalcula_preco_medio(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 50.0, "t1")
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "t2")
    pos = journal.get_open_positions("demo", "crypto")[0]
    # 2 unidades a 50 + 1 unidade a 100 = 3 unidades, média 66.67
    assert abs(pos["qty"] - 3.0) < 1e-9
    assert abs(pos["avg_price"] - 200 / 3) < 1e-6
    assert pos["thesis"] == "t2"  # tese mais recente prevalece


def test_venda_parcial_realiza_pnl(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 200, 100.0, "tese")
    pnl_usd, pnl_pct = journal.record_sell("demo", "crypto", "BTCUSDT", 110, 110.0, "decisao_ia")
    assert abs(pnl_usd - 10.0) < 1e-6      # vendeu 1 un. com +$10
    assert abs(pnl_pct - 10.0) < 1e-6
    pos = journal.get_open_positions("demo", "crypto")[0]
    assert abs(pos["qty"] - 1.0) < 1e-9    # restou 1 unidade


def test_venda_total_fecha_posicao(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "tese")
    journal.record_sell("demo", "crypto", "BTCUSDT", 90, 90.0, "stop_loss")
    assert journal.get_open_positions("demo", "crypto") == []


def test_residuo_de_poeira_fecha_posicao(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "tese")
    journal.record_sell("demo", "crypto", "BTCUSDT", 99.5, 100.0, "decisao_ia")
    assert journal.get_open_positions("demo", "crypto") == []  # sobrou $0.50 → poeira


def test_venda_sem_posicao_retorna_zero(journal):
    assert journal.record_sell("demo", "crypto", "XRPUSDT", 100, 1.0, "x") == (0.0, 0.0)


def test_venda_maior_que_posicao_limita_na_quantidade(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "tese")
    pnl_usd, _ = journal.record_sell("demo", "crypto", "BTCUSDT", 500, 110.0, "decisao_ia")
    assert abs(pnl_usd - 10.0) < 1e-6  # só tinha 1 unidade


def test_marks_atualizam_pico_e_ultimo_preco(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "tese")
    journal.update_position_marks("demo", "crypto", {"BTCUSDT": 120.0})
    journal.update_position_marks("demo", "crypto", {"BTCUSDT": 110.0})
    pos = journal.get_open_positions("demo", "crypto")[0]
    assert pos["peak_price"] == 120.0 and pos["last_price"] == 110.0


def test_realized_guarda_tese_e_conviccao(journal):
    journal.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "tese X", "high")
    journal.record_sell("demo", "crypto", "BTCUSDT", 110, 110.0, "take_profit")
    r = journal.realized_list("demo")[0]
    assert r["thesis"] == "tese X" and r["confidence"] == "high"


# ── métricas ────────────────────────────────────────────────────────
def test_realized_stats(journal):
    journal.record_buy("demo", "crypto", "A", 100, 100.0, "t")
    journal.record_sell("demo", "crypto", "A", 120, 120.0, "tp")    # +$20
    journal.record_buy("demo", "crypto", "B", 100, 100.0, "t")
    journal.record_sell("demo", "crypto", "B", 90, 90.0, "sl")      # -$10
    s = journal.realized_stats("demo")
    assert s["closed_trades"] == 2
    assert abs(s["realized_pnl_usd"] - 10.0) < 1e-6
    assert s["win_rate_pct"] == 50.0
    assert abs(s["profit_factor"] - 2.0) < 1e-6


def test_profit_factor_sem_perdas_eh_infinito(journal):
    journal.record_buy("demo", "crypto", "A", 100, 100.0, "t")
    journal.record_sell("demo", "crypto", "A", 120, 120.0, "tp")
    assert journal.realized_stats("demo")["profit_factor"] == float("inf")


def test_calibracao_por_conviccao(journal):
    journal.record_buy("demo", "crypto", "A", 100, 100.0, "t", "high")
    journal.record_sell("demo", "crypto", "A", 120, 120.0, "tp")
    journal.record_buy("demo", "crypto", "B", 100, 100.0, "t", "low")
    journal.record_sell("demo", "crypto", "B", 90, 90.0, "sl")
    cal = journal.confidence_calibration("demo")
    assert cal["high"]["win_rate_pct"] == 100.0
    assert cal["low"]["win_rate_pct"] == 0.0


def test_benchmark_buy_and_hold(journal):
    journal.log_prices("demo", "crypto", {"BTCUSDT": 100.0})
    journal.log_prices("demo", "crypto", {"BTCUSDT": 110.0})
    journal.log_prices("demo", "stocks", {"AAPL": 200.0})
    journal.log_prices("demo", "stocks", {"AAPL": 220.0})
    assert abs(journal.benchmark_return_pct("demo") - 10.0) < 1e-6


def test_benchmark_sem_dados(journal):
    assert journal.benchmark_return_pct("demo") is None


def test_equity_series_forward_fill(journal):
    journal.log_equity("demo", "crypto", 1000, 500)
    journal.log_equity("demo", "stocks", 2000, 900)
    journal.log_equity("demo", "crypto", 1100, 500)
    series = journal.equity_series("demo")
    # série começa quando os 2 mercados existem: [3000, 3100]
    assert [v for _, v in series] == [3000, 3100]


# ── eventos, lições e calendário ────────────────────────────────────
def test_eventos_recentes_e_janela(journal):
    journal.record_event("demo", "crypto", "BTCUSDT", "buy", "evento-x", "r")
    events = journal.recent_events("demo", days=3)
    assert events and events[0]["event_key"] == "evento-x"
    assert journal.recent_events("demo", days=0) == []


def test_licoes_salvas_e_recuperadas(journal):
    assert journal.latest_lessons("demo") is None
    journal.save_lessons("demo", "lição 1")
    journal.save_lessons("demo", "lição 2")
    assert journal.latest_lessons("demo")["lessons_text"] == "lição 2"


def test_calendario_cache(journal):
    assert journal.get_calendar("2026-06-10") is None
    journal.save_calendar("2026-06-10", "FOMC amanhã")
    assert journal.get_calendar("2026-06-10") == "FOMC amanhã"
    journal.save_calendar("2026-06-10", "atualizado")  # REPLACE não duplica
    assert journal.get_calendar("2026-06-10") == "atualizado"


def test_closed_trades_since(journal):
    journal.record_buy("demo", "crypto", "A", 100, 100.0, "t")
    journal.record_sell("demo", "crypto", "A", 120, 120.0, "tp")
    assert len(journal.closed_trades_since("demo", "2000-01-01")) == 1
    assert journal.closed_trades_since("demo", "2999-01-01") == []


def test_migracao_de_banco_antigo(tmp_path):
    """Banco criado sem as colunas novas deve ser migrado sem erro."""
    import sqlite3
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, market TEXT, symbol TEXT,
        qty REAL, avg_price REAL, last_price REAL, peak_price REAL,
        thesis TEXT, opened_at TEXT, updated_at TEXT, UNIQUE(mode, market, symbol))""")
    conn.commit(); conn.close()
    j = Journal(db)  # não pode explodir
    j.record_buy("demo", "crypto", "BTCUSDT", 100, 100.0, "t", "high")
    assert j.get_open_positions("demo", "crypto")


def test_losing_streak(journal):
    assert journal.losing_streak("demo") == 0
    for i, exit_price in enumerate([90.0, 95.0]):  # 2 perdas
        journal.record_buy("demo", "crypto", f"L{i}", 100, 100.0, "t")
        journal.record_sell("demo", "crypto", f"L{i}", exit_price, exit_price, "sl")
    assert journal.losing_streak("demo") == 2
    journal.record_buy("demo", "crypto", "W", 100, 100.0, "t")
    journal.record_sell("demo", "crypto", "W", 120, 120.0, "tp")  # vitória zera
    assert journal.losing_streak("demo") == 0
