"""Ponto de entrada do Phebos.

Comandos:
    python -m phebos.main run        # loop contínuo
    python -m phebos.main once       # um único ciclo (teste)
    python -m phebos.main evaluate   # relatório do período demo
    python -m phebos.main dashboard  # dashboard web em http://localhost:8000
"""

import logging
import os
import sys
import time

from .analyst import Analyst
from .brokers.alpaca import AlpacaBroker
from .brokers.base import Broker
from .brokers.binance import BinanceBroker
from .config import Settings, kill_switch_active, load_settings
from .evaluation import evaluate_demo, print_report
from .indicators import compute_indicators
from .journal import Journal
from .news import fetch_headlines, format_headlines
from .notify import Notifier
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


def run_cycle(settings: Settings, brokers, analyst: Analyst, risk: RiskEngine,
              journal: Journal, notifier: Notifier) -> None:
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

            # 1) manchetes RSS (rápido e gratuito)
            headlines = fetch_headlines(settings.news.feeds_for(market),
                                        settings.news.max_headlines_per_feed)
            log.info("[%s] %d manchetes coletadas via RSS", market, len(headlines))

            # 2) pesquisa ativa: Claude + web search → briefing de inteligência
            briefing = analyst.research(snapshot, format_headlines(headlines))
            journal.log_research(settings.mode, market, briefing)
            log.info("[%s] briefing: %s", market,
                     briefing[:300].replace("\n", " ") + ("…" if len(briefing) > 300 else ""))

            # 3) indicadores técnicos dos candles
            indicators = compute_indicators(snapshot)

            # 4) decisão estruturada
            decision = analyst.decide(snapshot, indicators, briefing, risk.summary())
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
                    notifier.vetoed(market, o.side, o.symbol, o.notional_usd, v.reason)
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
                notifier.trade(settings.mode, market, o.side, o.symbol,
                               o.notional_usd, o.rationale, executed.broker_order_id)
        except Exception as exc:
            log.exception("[%s] erro no ciclo — seguindo para o próximo mercado", market)
            notifier.error(market, str(exc))


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    command = sys.argv[1] if len(sys.argv) > 1 else "run"

    if command == "dashboard":
        from .dashboard import serve
        serve(port=int(os.environ.get("PHEBOS_DASHBOARD_PORT", "8000")))
        return

    settings = load_settings()
    journal = Journal()

    if command == "evaluate":
        print_report(evaluate_demo(journal, settings.demo))
        return

    brokers = build_brokers(settings)
    analyst = Analyst(
        settings.analyst_model,
        settings.analyst_extra_instructions,
        web_search=settings.analyst_web_search,
    )
    risk = RiskEngine(settings.risk)
    notifier = Notifier(settings.telegram_enabled)

    banner = "DINHEIRO REAL" if settings.is_live else "DEMO (dinheiro fictício)"
    market_names = [b.market for b, _ in brokers]
    log.info("Phebos iniciado — modo %s | intervalo %d min | mercados: %s",
             banner, settings.interval_minutes, ", ".join(market_names))
    notifier.startup(settings.mode, market_names, settings.interval_minutes)

    if command == "once":
        run_cycle(settings, brokers, analyst, risk, journal, notifier)
        return
    if command != "run":
        print(f"Comando desconhecido: {command} (use run | once | evaluate | dashboard)")
        sys.exit(1)

    while True:
        run_cycle(settings, brokers, analyst, risk, journal, notifier)
        time.sleep(settings.interval_minutes * 60)


if __name__ == "__main__":
    main()
