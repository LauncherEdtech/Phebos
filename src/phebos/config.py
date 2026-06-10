"""Carrega config.yaml + .env e aplica a trava de segurança do modo real."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# Em Docker, PHEBOS_DATA_DIR=/app/data persiste banco e kill switch num volume
DATA_DIR = Path(os.environ.get("PHEBOS_DATA_DIR", str(ROOT)))
KILL_FILE = DATA_DIR / "KILL"
DB_PATH = DATA_DIR / "phebos.db"

LIVE_CONFIRMATION = "EU_ACEITO_O_RISCO"


@dataclass
class RiskConfig:
    max_pct_per_trade: float = 5.0
    max_open_positions: int = 6
    max_daily_loss_pct: float = 3.0
    min_order_notional_usd: float = 10.0


@dataclass
class DemoConfig:
    min_days: int = 30
    min_trades: int = 20
    min_return_pct: float = 2.0
    max_drawdown_pct: float = 10.0


@dataclass
class MarketConfig:
    enabled: bool = False
    symbols: List[str] = field(default_factory=list)


@dataclass
class NewsConfig:
    max_headlines_per_feed: int = 8
    rss_feeds: dict = field(default_factory=dict)  # {"crypto": [...], "stocks": [...]}

    def feeds_for(self, market: str) -> List[str]:
        return list(self.rss_feeds.get(market, []))


@dataclass
class Settings:
    mode: str
    interval_minutes: int
    crypto: MarketConfig
    stocks: MarketConfig
    risk: RiskConfig
    demo: DemoConfig
    news: NewsConfig
    analyst_model: str
    analyst_extra_instructions: str
    analyst_web_search: bool
    telegram_enabled: bool

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    def broker_credentials(self, market: str) -> tuple[str, str]:
        """Retorna (api_key, api_secret) do ambiente conforme mercado e modo."""
        if market == "crypto":
            prefix = "BINANCE_LIVE" if self.is_live else "BINANCE_TESTNET"
        elif market == "stocks":
            prefix = "ALPACA_LIVE" if self.is_live else "ALPACA_PAPER"
        else:
            raise ValueError(f"mercado desconhecido: {market}")
        key = os.environ.get(f"{prefix}_API_KEY", "")
        secret = os.environ.get(f"{prefix}_API_SECRET", "")
        if not key or not secret:
            raise RuntimeError(
                f"Credenciais {prefix}_API_KEY / {prefix}_API_SECRET ausentes no .env"
            )
        return key, secret


def load_settings(path: Path | None = None) -> Settings:
    load_dotenv(ROOT / ".env")
    raw = yaml.safe_load((path or ROOT / "config.yaml").read_text())

    mode = raw.get("mode", "demo")
    if mode not in ("demo", "live"):
        raise ValueError(f"mode inválido no config.yaml: {mode!r}")
    if mode == "live" and os.environ.get("PHEBOS_CONFIRM_LIVE") != LIVE_CONFIRMATION:
        raise RuntimeError(
            "Modo LIVE bloqueado: para operar com dinheiro real defina "
            f"PHEBOS_CONFIRM_LIVE={LIVE_CONFIRMATION} no ambiente. "
            "Rode 'python -m phebos.main evaluate' para ver se o período demo "
            "atingiu os critérios antes de fazer a troca."
        )

    markets = raw.get("markets", {})
    analyst = raw.get("analyst", {})
    news = raw.get("news", {})
    return Settings(
        mode=mode,
        interval_minutes=int(raw.get("interval_minutes", 15)),
        crypto=MarketConfig(**markets.get("crypto", {})),
        stocks=MarketConfig(**markets.get("stocks", {})),
        risk=RiskConfig(**raw.get("risk", {})),
        demo=DemoConfig(**raw.get("demo", {})),
        news=NewsConfig(
            max_headlines_per_feed=int(news.get("max_headlines_per_feed", 8)),
            rss_feeds=news.get("rss_feeds", {}) or {},
        ),
        analyst_model=analyst.get("model", "gemini-2.5-flash"),
        analyst_extra_instructions=analyst.get("extra_instructions", "") or "",
        analyst_web_search=bool(analyst.get("web_search", True)),
        telegram_enabled=bool(raw.get("notifications", {}).get("telegram", True)),
    )


def kill_switch_active() -> bool:
    return KILL_FILE.exists()
