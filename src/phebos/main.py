"""Ponto de entrada do Phebos.

Comandos:
    python -m phebos.main run        # loop contínuo
    python -m phebos.main once       # um único ciclo (teste)
    python -m phebos.main evaluate   # relatório do período demo
"""

import logging
import sys
import time

from .analyst import Analyst
from .brokers.alpaca import AlpacaBroker
from .brokers.base import Broker
from .brokers.binance import BinanceBroker
from .config import Settings, kill_switch_active, load_settings
from .evaluation import evaluate_demo, print_report
from .journal import Journal
from .risk import RiskEngine

log = logging.getLogger("phebos")


def build_brokers(settings: Settings) -> list[tuple[Broker, list[str]]]:
    brokers: list[tuple[Broker, list[str]]] = []
    if settings.crypto.enabled:
        key, secret = settings.broker_credentials("crypto")
        brokers.append((BinanceBroker(key, secret, settings.is_live), settings.crypto.symbols))
    if settings.stocks.enabled:
        key, secret = settings.broker_credentials("stocks")
        brokers.append((AlpacaBroker(key, secret, settings.is_live), settings.stocks.symbols))
    if not brokers:
        raise RuntimeError("Nenhum mercado habilitado no config.yaml")
    return brokers


def run_cycle(settings: Settings, brokers, analyst: Analyst, risk: RiskEngine, journal: Journal) -> None:
    for broker, symbols in brokers:
        market = broker.market
        try:
            if not broker.is_market_open():
                log.info("[%s] mercado fechado — pulando", market)
                continue

            snapshot = broker.snapshot(symbols)
            journal.log_equity(settings.mode, market, snapshot.equity_usd, snapshot.cash_usd)
            log.info("[%s] patrimônio=$%.2f caixa=$%.2f posições=%d",
                     market, snapshot.equity_usd, snapshot.cash_usd, len(snapshot.positions))

            decision = analyst.decide(snapshot, risk.summary())
            journal.log_decision(settings.mode, market, decision.market_view, len(decision.orders))
            log.info("[%s] análise: %s", market, decision.market_view)

            if not decision.orders:
                log.info("[%s] decisão: não operar neste ciclo", market)
                continue

            daily_pnl = journal.daily_pnl_pct(settings.mode, market)
            verdicts = risk.review(decision.orders, snapshot, symbols, daily_pnl)
            for v in verdicts:
                o = v.order
                if not v.approved:
                    log.warning("[%s] ordem VETADA %s %s $%.2f — %s",
                                market, o.side, o.symbol, o.notional_usd, v.reason)
                    journal.log_trade(settings.mode, market, o.symbol, o.side,
                                      o.notional_usd, False, v.reason, o.rationale)
                    continue
                if kill_switch_active():
                    log.warning("[%s] kill switch ativo — ordem não enviada", market)
                    continue
                executed = broker.execute(o)
                log.info("[%s] EXECUTADA %s %s $%.2f (id=%s) — %s",
                         market, o.side, o.symbol, o.notional_usd,
                         executed.broker_order_id, o.rationale)
                journal.log_trade(settings.mode, market, o.symbol, o.side, o.notional_usd,
                                  True, "ok", o.rationale, executed.broker_order_id)
        except Exception:
            log.exception("[%s] erro no ciclo — seguindo para o próximo mercado", market)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    settings = load_settings()
    journal = Journal()

    if command == "evaluate":
        print_report(evaluate_demo(journal, settings.demo))
        return

    brokers = build_brokers(settings)
    analyst = Analyst(settings.analyst_model, settings.analyst_extra_instructions)
    risk = RiskEngine(settings.risk)

    banner = "DINHEIRO REAL" if settings.is_live else "DEMO (dinheiro fictício)"
    log.info("Phebos iniciado — modo %s | intervalo %d min | mercados: %s",
             banner, settings.interval_minutes,
             ", ".join(b.market for b, _ in brokers))

    if command == "once":
        run_cycle(settings, brokers, analyst, risk, journal)
        return
    if command != "run":
        print(f"Comando desconhecido: {command} (use run | once | evaluate)")
        sys.exit(1)

    while True:
        run_cycle(settings, brokers, analyst, risk, journal)
        time.sleep(settings.interval_minutes * 60)


if __name__ == "__main__":
    main()
