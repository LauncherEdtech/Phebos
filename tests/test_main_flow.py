"""Teste de integração do fluxo completo do agente (broker e IA simulados)."""

import logging

from phebos import main as pm
from phebos.brokers.base import Broker, ExecutedOrder
from phebos.config import DemoConfig, MarketConfig, NewsConfig, RiskConfig, Settings
from phebos.notify import Notifier
from phebos.risk import RiskEngine
from phebos.schemas import OrderDecision, TradingDecision
from conftest import make_snapshot

logging.disable(logging.CRITICAL)


class FakeBroker(Broker):
    market = "crypto"

    def __init__(self, price_ref):
        self.price_ref = price_ref
        self.executed = []
        self.open = True

    def is_market_open(self):
        return self.open

    def snapshot(self, symbols):
        return make_snapshot(price=self.price_ref["v"],
                             prices_1h=[self.price_ref["v"]] * 24)

    def execute(self, order):
        self.executed.append(order)
        return ExecutedOrder(order.symbol, order.side, order.notional_usd, "ord-1")


class FakeAnalyst:
    def __init__(self, orders=None):
        self.orders = orders or []
        self.contexts = []

    def research(self, snapshot, headlines):
        return "briefing de teste"

    def calendar_briefing(self, symbols):
        return "FOMC amanhã"

    def reflect(self, closed, calibration):
        return "lição de teste"

    def decide(self, snapshot, indicators, briefing, risk_summary, context=None):
        self.contexts.append(context or {})
        return TradingDecision(market_view="visão de teste", orders=list(self.orders))


def make_settings(**risk_kw):
    return Settings(
        mode="demo", interval_minutes=15,
        crypto=MarketConfig(True, ["BTCUSDT"]), stocks=MarketConfig(False, []),
        risk=RiskConfig(**risk_kw), demo=DemoConfig(),
        news=NewsConfig(rss_feeds={"crypto": []}),
        analyst_model="x", analyst_extra_instructions="",
        analyst_web_search=False, telegram_enabled=False,
        sentiment_enabled=False, reddit_subs={}, calendar_enabled=True,
        reflection_every_days=7,
    )


def run(settings, broker, analyst, journal):
    pm.run_cycle(settings, [(broker, ["BTCUSDT"])], analyst,
                 RiskEngine(settings.risk), journal, Notifier(False))


def buy_order(notional=40, key="evento-1"):
    return OrderDecision(symbol="BTCUSDT", side="buy", notional_usd=notional,
                         confidence="high", rationale="noticia forte", event_key=key)


def test_fluxo_compra_registra_tudo(journal):
    price = {"v": 100.0}
    broker = FakeBroker(price)
    analyst = FakeAnalyst([buy_order()])
    run(make_settings(), broker, analyst, journal)

    assert len(broker.executed) == 1
    pos = journal.get_open_positions("demo", "crypto")[0]
    assert pos["thesis"] == "noticia forte"
    assert journal.recent_events("demo", 3)[0]["event_key"] == "evento-1"
    assert journal.get_calendar.__self__ is journal  # sanity
    # calendário entrou no contexto da decisão
    assert analyst.contexts[0]["calendar"] == "FOMC amanhã"


def test_fluxo_dedupe_no_segundo_ciclo(journal):
    price = {"v": 100.0}
    broker = FakeBroker(price)
    analyst = FakeAnalyst([buy_order()])
    settings = make_settings()
    run(settings, broker, analyst, journal)
    run(settings, broker, analyst, journal)
    assert len(broker.executed) == 1  # segunda compra vetada pelo dedupe
    vetoed = journal.conn.execute("SELECT COUNT(*) FROM trades WHERE approved=0").fetchone()[0]
    assert vetoed == 1


def test_fluxo_stop_loss_automatico(journal):
    price = {"v": 100.0}
    broker = FakeBroker(price)
    analyst = FakeAnalyst([buy_order()])
    settings = make_settings(stop_loss_pct=8)
    run(settings, broker, analyst, journal)

    price["v"] = 90.0
    analyst.orders = []  # IA não propõe nada; o stop tem que agir sozinho
    run(settings, broker, analyst, journal)

    sells = [o for o in broker.executed if o.side == "sell"]
    assert len(sells) == 1
    realized = journal.realized_list("demo")[0]
    assert realized["reason"] == "stop_loss" and realized["pnl_pct"] < -9


def test_fluxo_mercado_fechado_nao_opera(journal):
    broker = FakeBroker({"v": 100.0})
    broker.open = False
    analyst = FakeAnalyst([buy_order()])
    run(make_settings(), broker, analyst, journal)
    assert broker.executed == []


def test_fluxo_kill_switch_bloqueia_tudo(journal, monkeypatch):
    monkeypatch.setattr(pm, "kill_switch_active", lambda: True)
    monkeypatch.setattr("phebos.risk.kill_switch_active", lambda: True)
    broker = FakeBroker({"v": 100.0})
    analyst = FakeAnalyst([buy_order()])
    run(make_settings(), broker, analyst, journal)
    assert broker.executed == []


def test_fluxo_erro_no_broker_nao_derruba_ciclo(journal):
    class BrokenBroker(FakeBroker):
        def snapshot(self, symbols):
            raise RuntimeError("API fora do ar")
    broker = BrokenBroker({"v": 100.0})
    analyst = FakeAnalyst([buy_order()])
    run(make_settings(), broker, analyst, journal)  # não pode levantar exceção


def test_fluxo_reflexao_alimenta_contexto(journal):
    # fecha 3 trades para habilitar a reflexão
    for i in range(3):
        journal.record_buy("demo", "crypto", f"S{i}", 100, 100.0, "t", "high")
        journal.record_sell("demo", "crypto", f"S{i}", 110, 110.0, "take_profit")
    broker = FakeBroker({"v": 100.0})
    analyst = FakeAnalyst()
    run(make_settings(), broker, analyst, journal)
    ctx = analyst.contexts[0]
    assert ctx["lessons"] == "lição de teste"
    assert ctx["calibration"]["high"]["trades"] == 3


def test_fluxo_redimensionamento_aplicado_na_execucao(journal):
    broker = FakeBroker({"v": 100.0})
    analyst = FakeAnalyst([buy_order(notional=500)])  # acima do teto de 5%
    run(make_settings(), broker, analyst, journal)
    assert len(broker.executed) == 1
    assert broker.executed[0].notional_usd <= 50.0  # redimensionada p/ teto


def test_journal_log_handler_espelha_logs(journal):
    import logging as logmod
    handler = pm.JournalLogHandler(journal)
    logger = logmod.getLogger("phebos.teste")
    logger.addHandler(handler)
    logger.setLevel(logmod.INFO)
    logmod.disable(logmod.NOTSET)  # reabilita (módulo desativa no topo)
    try:
        logger.info("mensagem %s", "formatada")
        logger.error("falhou", exc_info=(ValueError, ValueError("x"), None))
    finally:
        logmod.disable(logmod.CRITICAL)
        logger.removeHandler(handler)
    logs = journal.get_logs()
    assert any("mensagem formatada" in l["message"] for l in logs)
    assert any("ValueError" in l["message"] for l in logs)


def test_log_handler_tolera_journal_quebrado():
    import logging as logmod

    class BrokenJournal:
        def write_log(self, *a):
            raise RuntimeError("banco fora")

    handler = pm.JournalLogHandler(BrokenJournal())
    record = logmod.LogRecord("x", logmod.INFO, "f", 1, "msg", None, None)
    handler.emit(record)  # não pode levantar exceção


def test_init_falha_com_erro_claro_sem_chaves(monkeypatch):
    """Sem chaves do mercado habilitado, a inicialização levanta erro claro —
    que o loop autocurável do main() loga na aba Logs e tenta de novo."""
    import pytest
    for f in ("BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET"):
        monkeypatch.delenv(f, raising=False)
    with pytest.raises(RuntimeError, match="BINANCE_TESTNET"):
        pm.build_brokers(make_settings())


def test_key_summary_mostra_presenca_sem_expor_valores(monkeypatch, tmp_path):
    import importlib
    monkeypatch.setenv("PHEBOS_DATA_DIR", str(tmp_path))
    import phebos.config, phebos.keys
    importlib.reload(phebos.config)
    importlib.reload(phebos.keys)
    for f in phebos.keys.KEY_FIELDS:
        monkeypatch.delenv(f, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "chave-super-secreta")
    s = pm.key_summary()
    assert "Gemini ✔" in s
    assert "Binance-testnet ✖" in s
    assert "chave-super-secreta" not in s
