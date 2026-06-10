"""Interface comum de corretora/exchange."""

from abc import ABC, abstractmethod
from typing import List

from ..schemas import MarketSnapshot, OrderDecision


class ExecutedOrder:
    def __init__(self, symbol: str, side: str, notional_usd: float, broker_order_id: str):
        self.symbol = symbol
        self.side = side
        self.notional_usd = notional_usd
        self.broker_order_id = broker_order_id


class Broker(ABC):
    market: str  # "crypto" | "stocks"

    @abstractmethod
    def is_market_open(self) -> bool:
        """Cripto é sempre True; ações dependem do pregão."""

    @abstractmethod
    def snapshot(self, symbols: List[str]) -> MarketSnapshot:
        """Coleta preços, candles, posições e saldo."""

    @abstractmethod
    def execute(self, order: OrderDecision) -> ExecutedOrder:
        """Envia uma ordem a mercado já aprovada pelo motor de risco."""
