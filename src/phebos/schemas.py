"""Modelos de dados: snapshot de mercado e decisão estruturada da IA."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Candle(BaseModel):
    open_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class SymbolData(BaseModel):
    symbol: str
    last_price: float
    change_24h_pct: Optional[float] = None
    candles: List[Candle] = Field(default_factory=list)        # 1h
    candles_4h: List[Candle] = Field(default_factory=list)     # visão intermediária
    candles_1d: List[Candle] = Field(default_factory=list)     # tendência maior


class Position(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    market_value: float
    unrealized_pnl: float


class MarketSnapshot(BaseModel):
    market: Literal["crypto", "stocks"]
    timestamp: str
    equity_usd: float
    cash_usd: float
    positions: List[Position]
    symbols: List[SymbolData]


class OrderDecision(BaseModel):
    """Uma ordem proposta pela IA — sempre validada pelo motor de risco antes de executar."""

    symbol: str
    side: Literal["buy", "sell"]
    notional_usd: float = Field(description="Valor da ordem em dólares")
    confidence: Literal["low", "medium", "high"]
    rationale: str = Field(description="Justificativa curta e objetiva da ordem")
    event_key: Optional[str] = Field(
        default=None,
        description=(
            "Identificador curto e estável do EVENTO de notícia que motivou a ordem, "
            "em kebab-case (ex.: 'eua-reserva-estrategica-btc'). Use null se a ordem "
            "for puramente técnica, sem notícia motivadora."
        ),
    )


class TradingDecision(BaseModel):
    """Resposta estruturada do analista (Claude) para um ciclo de análise."""

    market_view: str = Field(description="Leitura geral do mercado neste momento, em 2-3 frases")
    orders: List[OrderDecision] = Field(
        default_factory=list,
        description="Ordens propostas. Lista vazia significa: não operar neste ciclo.",
    )
