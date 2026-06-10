from datetime import datetime, timedelta, timezone

from phebos.config import DemoConfig
from phebos.evaluation import evaluate_demo, print_report
from phebos.intelligence import get_daily_calendar, maybe_reflect


class FakeAnalyst:
    def __init__(self):
        self.calendar_calls = 0
        self.reflect_calls = 0

    def calendar_briefing(self, symbols):
        self.calendar_calls += 1
        return "FOMC quarta-feira; earnings NVDA quinta."

    def reflect(self, closed, calibration):
        self.reflect_calls += 1
        return "Lição: não comprar notícia velha."


# ── calendário ──────────────────────────────────────────────────────
def test_calendario_busca_uma_vez_e_cacheia(journal):
    a = FakeAnalyst()
    t1 = get_daily_calendar(journal, a, ["BTCUSDT"])
    t2 = get_daily_calendar(journal, a, ["BTCUSDT"])
    assert t1 == t2 == "FOMC quarta-feira; earnings NVDA quinta."
    assert a.calendar_calls == 1  # segunda chamada veio do cache


def test_calendario_desativado(journal):
    a = FakeAnalyst()
    assert get_daily_calendar(journal, a, ["BTCUSDT"], enabled=False) == ""
    assert a.calendar_calls == 0


def test_calendario_falha_tolerada(journal):
    class Boom:
        def calendar_briefing(self, s):
            raise RuntimeError("api fora")
    assert get_daily_calendar(journal, Boom(), ["BTCUSDT"]) == ""


# ── auto-reflexão ───────────────────────────────────────────────────
def _close_n_trades(journal, n):
    for i in range(n):
        journal.record_buy("demo", "crypto", f"S{i}", 100, 100.0, f"tese {i}", "high")
        journal.record_sell("demo", "crypto", f"S{i}", 110, 110.0, "take_profit")


def test_reflexao_dispara_com_trades_suficientes(journal):
    a = FakeAnalyst()
    _close_n_trades(journal, 3)
    lessons = maybe_reflect(journal, a, "demo", every_days=7)
    assert a.reflect_calls == 1
    assert "Lição" in lessons
    assert journal.latest_lessons("demo")["lessons_text"] == lessons


def test_reflexao_nao_repete_antes_do_prazo(journal):
    a = FakeAnalyst()
    _close_n_trades(journal, 3)
    maybe_reflect(journal, a, "demo", every_days=7)
    lessons2 = maybe_reflect(journal, a, "demo", every_days=7)
    assert a.reflect_calls == 1  # segunda chamada usa a lição existente
    assert "Lição" in lessons2


def test_reflexao_exige_minimo_de_trades(journal):
    a = FakeAnalyst()
    _close_n_trades(journal, 1)
    assert maybe_reflect(journal, a, "demo", every_days=7, min_trades=3) == ""
    assert a.reflect_calls == 0


def test_reflexao_falha_tolerada(journal):
    class Boom:
        def reflect(self, c, cal):
            raise RuntimeError("api fora")
    _close_n_trades(journal, 3)
    assert maybe_reflect(journal, Boom(), "demo") == ""


# ── avaliação ───────────────────────────────────────────────────────
def test_evaluate_sem_dados(journal):
    assert evaluate_demo(journal, DemoConfig()) is None


def test_evaluate_com_benchmark(journal):
    journal.log_equity("demo", "crypto", 1000, 500)
    journal.log_equity("demo", "crypto", 1100, 500)          # agente: +10%
    journal.log_prices("demo", "crypto", {"BTCUSDT": 100.0})
    journal.log_prices("demo", "crypto", {"BTCUSDT": 120.0})  # mercado: +20%
    report = evaluate_demo(journal, DemoConfig())
    assert abs(report.return_pct - 10.0) < 1e-6
    assert abs(report.benchmark_return_pct - 20.0) < 1e-6
    assert abs(report.alpha_pct - (-10.0)) < 1e-6
    # critério de benchmark deve reprovar (10% < 20%)
    bench_criterion = [ok for label, ok in report.criteria if "buy-and-hold" in label][0]
    assert not bench_criterion


def test_evaluate_sem_benchmark_quando_desligado(journal):
    journal.log_equity("demo", "crypto", 1000, 500)
    journal.log_equity("demo", "crypto", 1100, 500)
    journal.log_prices("demo", "crypto", {"BTCUSDT": 100.0})
    journal.log_prices("demo", "crypto", {"BTCUSDT": 120.0})
    report = evaluate_demo(journal, DemoConfig(must_beat_benchmark=False))
    assert not any("buy-and-hold" in label for label, _ in report.criteria)


def test_print_report_nao_explode(journal, capsys):
    print_report(None)
    journal.log_equity("demo", "crypto", 1000, 500)
    journal.log_equity("demo", "crypto", 1100, 500)
    print_report(evaluate_demo(journal, DemoConfig()))
    out = capsys.readouterr().out
    assert "Relatório do período demo" in out
