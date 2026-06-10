"""Motor de risco determinístico — a última palavra antes de qualquer ordem.

A IA propõe; este módulo dispõe. Nenhuma regra aqui depende do modelo.
"""

from dataclasses import dataclass
from typing import List

from .config import RiskConfig, kill_switch_active
from .schemas import MarketSnapshot, OrderDecision


@dataclass
class RiskVerdict:
    order: OrderDecision
    approved: bool
    reason: str


@dataclass
class ExitSignal:
    """Venda forçada gerada pela disciplina de saída (independe da IA)."""

    symbol: str
    notional_usd: float
    reason: str      # stop_loss | take_profit | trailing_stop
    rationale: str


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config

    def summary(self) -> str:
        c = self.config
        trailing = (f"- trailing stop de {c.trailing_stop_pct}% abaixo do pico\n"
                    if c.trailing_stop_pct > 0 else "")
        return (
            f"- máx. {c.max_pct_per_trade}% do patrimônio por ordem\n"
            f"- máx. {c.max_open_positions} posições abertas\n"
            f"- perda diária máxima de {c.max_daily_loss_pct}% (depois disso, sem novas ordens no dia)\n"
            f"- ordem mínima de ${c.min_order_notional_usd}\n"
            f"- stop-loss automático em -{c.stop_loss_pct}% e take-profit em +{c.take_profit_pct}%\n"
            f"{trailing}"
            f"- o mesmo evento de notícia não é operado de novo por {c.event_dedup_days} dias"
        )

    # ── disciplina de saída: roda ANTES da IA, em código ───────────
    def check_exits(self, positions: list[dict], prices: dict[str, float]) -> list[ExitSignal]:
        """Avalia stop-loss, take-profit e trailing stop das posições abertas.

        Vendas de proteção fecham a posição inteira e NÃO passam pelo limite
        de perda diária — reduzir risco é sempre permitido.
        """
        c = self.config
        signals: list[ExitSignal] = []
        for pos in positions:
            price = prices.get(pos["symbol"])
            if not price or pos["avg_price"] <= 0:
                continue
            change_pct = (price - pos["avg_price"]) / pos["avg_price"] * 100
            notional = pos["qty"] * price

            if change_pct <= -c.stop_loss_pct:
                signals.append(ExitSignal(
                    pos["symbol"], notional, "stop_loss",
                    f"Stop-loss: {change_pct:+.2f}% vs preço médio "
                    f"${pos['avg_price']:.4f} (limite -{c.stop_loss_pct}%)",
                ))
            elif change_pct >= c.take_profit_pct:
                signals.append(ExitSignal(
                    pos["symbol"], notional, "take_profit",
                    f"Take-profit: {change_pct:+.2f}% vs preço médio "
                    f"${pos['avg_price']:.4f} (alvo +{c.take_profit_pct}%)",
                ))
            elif c.trailing_stop_pct > 0 and pos["peak_price"] > 0:
                drop_from_peak = (price - pos["peak_price"]) / pos["peak_price"] * 100
                if drop_from_peak <= -c.trailing_stop_pct:
                    signals.append(ExitSignal(
                        pos["symbol"], notional, "trailing_stop",
                        f"Trailing stop: {drop_from_peak:+.2f}% vs pico "
                        f"${pos['peak_price']:.4f} (limite -{c.trailing_stop_pct}%)",
                    ))
        return signals

    # multiplicadores do dimensionamento dinâmico (determinísticos)
    CONVICTION_MULT = {"high": 1.0, "medium": 0.7, "low": 0.4}
    REGIME_MULT_BUY = {"alta": 1.0, "lateral": 0.8, "baixa": 0.5}

    def position_cap_usd(self, equity_usd: float, confidence: str,
                         atr_pct: float | None, regime: str,
                         loss_streak: int = 0) -> float:
        """Teto da ordem = base × convicção × escala de volatilidade × regime × anti-tilt.

        - convicção alta → posição cheia; baixa → 40% do teto
        - ativo mais volátil que o alvo (ATR) → posição menor (e vice-versa, limitado)
        - regime de baixa → compras pela metade
        - circuit breaker anti-tilt: sequência de perdas → sizing reduzido até
          a próxima saída vencedora (disciplina de mesa profissional)
        """
        c = self.config
        base = equity_usd * c.max_pct_per_trade / 100
        conviction = self.CONVICTION_MULT.get(confidence, 0.7)
        vol_scalar = 1.0
        if atr_pct and atr_pct > 0:
            vol_scalar = max(0.5, min(1.25, c.vol_target_atr_pct / atr_pct))
        regime_mult = self.REGIME_MULT_BUY.get(regime, 0.8)
        tilt_mult = c.loss_streak_factor if loss_streak >= c.loss_streak_threshold else 1.0
        return base * conviction * vol_scalar * regime_mult * tilt_mult

    def review(
        self,
        orders: List[OrderDecision],
        snapshot: MarketSnapshot,
        allowed_symbols: List[str],
        daily_pnl_pct: float,
        acted_events: set[tuple[str, str, str]] | None = None,
        atr_by_symbol: dict[str, float] | None = None,
        regime: str = "lateral",
        loss_streak: int = 0,
    ) -> List[RiskVerdict]:
        verdicts: List[RiskVerdict] = []
        open_symbols = {p.symbol for p in snapshot.positions}
        acted_events = acted_events or set()
        atr_by_symbol = atr_by_symbol or {}
        c = self.config

        for order in orders:
            if kill_switch_active():
                verdicts.append(RiskVerdict(order, False, "kill switch ativo (arquivo KILL presente)"))
                continue
            if order.event_key and (order.symbol, order.side, order.event_key) in acted_events:
                verdicts.append(RiskVerdict(
                    order, False,
                    f"evento '{order.event_key}' já foi operado nos últimos "
                    f"{c.event_dedup_days} dias (dedupe de notícias)",
                ))
                continue
            if daily_pnl_pct <= -c.max_daily_loss_pct:
                verdicts.append(RiskVerdict(
                    order, False,
                    f"perda diária de {daily_pnl_pct:.2f}% atingiu o limite de {c.max_daily_loss_pct}%",
                ))
                continue
            if order.symbol not in allowed_symbols:
                verdicts.append(RiskVerdict(order, False, f"símbolo {order.symbol} fora da lista permitida"))
                continue
            if order.notional_usd < c.min_order_notional_usd:
                verdicts.append(RiskVerdict(order, False, f"ordem abaixo do mínimo de ${c.min_order_notional_usd}"))
                continue
            # dimensionamento dinâmico: convicção × volatilidade (ATR) × regime.
            # Ordens acima do teto são REDIMENSIONADAS para baixo, não vetadas.
            sized_note = "ok"
            if order.side == "buy":
                cap = self.position_cap_usd(snapshot.equity_usd, order.confidence,
                                            atr_by_symbol.get(order.symbol), regime,
                                            loss_streak)
                if order.notional_usd > cap:
                    if cap < c.min_order_notional_usd:
                        verdicts.append(RiskVerdict(
                            order, False,
                            f"teto dimensionado (${cap:.2f}: convicção {order.confidence}, "
                            f"ATR {atr_by_symbol.get(order.symbol, '?')}%, regime {regime}) "
                            f"ficou abaixo da ordem mínima",
                        ))
                        continue
                    sized_note = (f"redimensionada de ${order.notional_usd:.2f} para ${cap:.2f} "
                                  f"(convicção {order.confidence}, "
                                  f"ATR {atr_by_symbol.get(order.symbol, '?')}%, regime {regime})")
                    order.notional_usd = round(cap, 2)
            if order.side == "buy":
                if order.symbol not in open_symbols and len(open_symbols) >= c.max_open_positions:
                    verdicts.append(RiskVerdict(order, False, f"já há {len(open_symbols)} posições abertas (máx. {c.max_open_positions})"))
                    continue
                if order.notional_usd > snapshot.cash_usd:
                    verdicts.append(RiskVerdict(order, False, f"caixa insuficiente (${snapshot.cash_usd:.2f})"))
                    continue
            if order.side == "sell" and order.symbol not in open_symbols:
                verdicts.append(RiskVerdict(order, False, "venda de ativo sem posição aberta"))
                continue

            verdicts.append(RiskVerdict(order, True, sized_note))
            if order.side == "buy":
                open_symbols.add(order.symbol)
        return verdicts
