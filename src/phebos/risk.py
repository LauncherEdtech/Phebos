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


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config

    def summary(self) -> str:
        c = self.config
        return (
            f"- máx. {c.max_pct_per_trade}% do patrimônio por ordem\n"
            f"- máx. {c.max_open_positions} posições abertas\n"
            f"- perda diária máxima de {c.max_daily_loss_pct}% (depois disso, sem novas ordens no dia)\n"
            f"- ordem mínima de ${c.min_order_notional_usd}"
        )

    def review(
        self,
        orders: List[OrderDecision],
        snapshot: MarketSnapshot,
        allowed_symbols: List[str],
        daily_pnl_pct: float,
    ) -> List[RiskVerdict]:
        verdicts: List[RiskVerdict] = []
        open_symbols = {p.symbol for p in snapshot.positions}
        c = self.config

        for order in orders:
            if kill_switch_active():
                verdicts.append(RiskVerdict(order, False, "kill switch ativo (arquivo KILL presente)"))
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
            max_notional = snapshot.equity_usd * c.max_pct_per_trade / 100
            if order.notional_usd > max_notional:
                verdicts.append(RiskVerdict(
                    order, False,
                    f"${order.notional_usd:.2f} excede o limite de ${max_notional:.2f} "
                    f"({c.max_pct_per_trade}% do patrimônio)",
                ))
                continue
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

            verdicts.append(RiskVerdict(order, True, "ok"))
            if order.side == "buy":
                open_symbols.add(order.symbol)
        return verdicts
