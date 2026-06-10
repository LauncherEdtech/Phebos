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
from .config import SECRETS_FILE, Settings, kill_switch_active, load_settings
from .evaluation import evaluate_demo, print_report
from .indicators import atr_by_symbol, compute_indicators
from .intelligence import get_daily_calendar, maybe_reflect
from .journal import Journal
from .news import fetch_headlines, format_headlines
from .notify import Notifier
from .risk import RiskEngine
from .schemas import OrderDecision
from . import sentiment as sentiment_mod

log = logging.getLogger("phebos")


class JournalLogHandler(logging.Handler):
    """Espelha os logs do agente no SQLite para a aba 'Logs' do dashboard.

    Falhas de escrita são engolidas — registrar log nunca pode derrubar o ciclo.
    """

    def __init__(self, journal: Journal):
        super().__init__(level=logging.INFO)
        self.journal = journal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                message += f" | {record.exc_info[0].__name__}: {record.exc_info[1]}"
            self.journal.write_log(record.levelname, message)
        except Exception:
            pass


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
    # inteligência global do ciclo: calendário (cache diário) e auto-reflexão
    all_symbols = [s for _, syms in brokers for s in syms]
    calendar_text = get_daily_calendar(journal, analyst, all_symbols,
                                       settings.calendar_enabled)
    lessons_text = maybe_reflect(journal, analyst, settings.mode,
                                 settings.reflection_every_days)

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

            # 1) marca preços e atualiza picos (benchmark + trailing stop)
            prices = {s.symbol: s.last_price for s in snapshot.symbols}
            journal.log_prices(settings.mode, market, prices)
            journal.update_position_marks(settings.mode, market, prices)

            # 2) DISCIPLINA DE SAÍDA: stop-loss/take-profit/trailing em código,
            #    antes e independente da IA
            for sig in risk.check_exits(journal.get_open_positions(settings.mode, market), prices):
                if kill_switch_active():
                    log.warning("[%s] kill switch ativo — saída %s de %s não enviada",
                                market, sig.reason, sig.symbol)
                    continue
                order = OrderDecision(symbol=sig.symbol, side="sell",
                                      notional_usd=sig.notional_usd,
                                      confidence="high", rationale=sig.rationale)
                executed = broker.execute(order)
                pnl_usd, pnl_pct = journal.record_sell(
                    settings.mode, market, sig.symbol, sig.notional_usd,
                    prices[sig.symbol], sig.reason)
                journal.log_trade(settings.mode, market, sig.symbol, "sell",
                                  sig.notional_usd, True, sig.reason, sig.rationale,
                                  executed.broker_order_id)
                log.info("[%s] SAÍDA AUTOMÁTICA (%s) %s $%.2f | P&L $%.2f (%+.2f%%)",
                         market, sig.reason, sig.symbol, sig.notional_usd, pnl_usd, pnl_pct)
                notifier.exit_order(settings.mode, market, sig.symbol, sig.reason,
                                    sig.notional_usd, pnl_usd, pnl_pct)

            # 3) manchetes RSS (rápido e gratuito)
            headlines = fetch_headlines(settings.news.feeds_for(market),
                                        settings.news.max_headlines_per_feed)
            log.info("[%s] %d manchetes coletadas via RSS", market, len(headlines))

            # 4) pesquisa ativa: Gemini + Busca Google → briefing de inteligência
            briefing = analyst.research(snapshot, format_headlines(headlines))
            journal.log_research(settings.mode, market, briefing)
            log.info("[%s] briefing: %s", market,
                     briefing[:300].replace("\n", " ") + ("…" if len(briefing) > 300 else ""))

            # 5) indicadores multi-timeframe + regime do mercado
            indicators = compute_indicators(snapshot)
            regime = indicators.get("_market_regime", "lateral")
            log.info("[%s] regime do mercado: %s", market, regime)

            # 6) sentimento social (Reddit / StockTwits / Fear & Greed)
            sentiment_text = ""
            if settings.sentiment_enabled:
                sentiment_text = sentiment_mod.collect(
                    market, symbols, settings.reddit_subs_for(market))

            # 7) decisão estruturada com MEMÓRIA + inteligência adicional
            open_positions = journal.get_open_positions(settings.mode, market)
            recent = journal.recent_decisions(settings.mode, market, limit=5)
            acted = journal.recent_events(settings.mode, settings.risk.event_dedup_days)
            context = {
                "open_positions": open_positions,
                "recent_decisions": recent,
                "acted_events": acted,
                "lessons": lessons_text,
                "calibration": journal.confidence_calibration(settings.mode),
                "calendar": calendar_text,
                "sentiment": sentiment_text,
            }
            decision = analyst.decide(snapshot, indicators, briefing,
                                      risk.summary(), context)
            journal.log_decision(settings.mode, market, decision.market_view, len(decision.orders))
            log.info("[%s] análise: %s", market, decision.market_view)

            if not decision.orders:
                log.info("[%s] decisão: não operar neste ciclo", market)
                continue

            daily_pnl = journal.daily_pnl_pct(settings.mode, market)
            acted_keys = {(e["symbol"], e["side"], e["event_key"]) for e in acted}
            loss_streak = journal.losing_streak(settings.mode)
            if loss_streak >= settings.risk.loss_streak_threshold:
                log.warning("[%s] anti-tilt ativo: %d perdas consecutivas — sizing reduzido",
                            market, loss_streak)
            verdicts = risk.review(decision.orders, snapshot, symbols, daily_pnl,
                                   acted_keys, atr_by_symbol(indicators), regime,
                                   loss_streak)
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
                # livro de posições: tese na compra, P&L realizado na venda
                price = prices.get(o.symbol)
                if price:
                    if o.side == "buy":
                        journal.record_buy(settings.mode, market, o.symbol,
                                           o.notional_usd, price, o.rationale,
                                           o.confidence)
                    else:
                        pnl_usd, pnl_pct = journal.record_sell(
                            settings.mode, market, o.symbol, o.notional_usd,
                            price, "decisao_ia")
                        log.info("[%s] P&L realizado em %s: $%.2f (%+.2f%%)",
                                 market, o.symbol, pnl_usd, pnl_pct)
                if o.event_key:
                    journal.record_event(settings.mode, market, o.symbol,
                                         o.side, o.event_key, o.rationale)
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

    # logs do agente também vão para o banco (aba "Logs" do dashboard)
    logging.getLogger().addHandler(JournalLogHandler(journal))
    journal.prune_logs()

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

    def secrets_mtime() -> float:
        try:
            return SECRETS_FILE.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    last_secrets = secrets_mtime()
    while True:
        run_cycle(settings, brokers, analyst, risk, journal, notifier)
        journal.prune_logs()

        # chaves salvas pela aba Conexões do dashboard → recarrega sem reiniciar
        if secrets_mtime() != last_secrets:
            last_secrets = secrets_mtime()
            log.info("chaves atualizadas pelo dashboard — recarregando conexões")
            try:
                settings = load_settings()
                brokers = build_brokers(settings)
                analyst = Analyst(settings.analyst_model,
                                  settings.analyst_extra_instructions,
                                  web_search=settings.analyst_web_search)
                notifier = Notifier(settings.telegram_enabled)
                log.info("conexões recarregadas com sucesso")
            except Exception:
                log.exception("falha ao recarregar chaves — mantendo configuração anterior")

        time.sleep(settings.interval_minutes * 60)


if __name__ == "__main__":
    main()
