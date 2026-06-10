"""Carrega config.yaml + .env e aplica a trava de segurança do modo real."""

import json
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
# Chaves salvas pelo dashboard (aba Conexões) — têm prioridade sobre o .env
SECRETS_FILE = DATA_DIR / "secrets.env"
# Controle do ciclo pelo dashboard: intervalo dinâmico e pedido de "rodar agora"
RUNTIME_FILE = DATA_DIR / "runtime.json"
RUN_NOW_FILE = DATA_DIR / "RUN_NOW"

LIVE_CONFIRMATION = "EU_ACEITO_O_RISCO"



@dataclass
class RiskConfig:
    max_pct_per_trade: float = 5.0
    max_open_positions: int = 6
    max_daily_loss_pct: float = 3.0
    min_order_notional_usd: float = 10.0
    stop_loss_pct: float = 8.0       # venda forçada se cair X% abaixo do preço médio
    take_profit_pct: float = 15.0    # venda forçada se subir X% acima do preço médio
    trailing_stop_pct: float = 0.0   # venda se cair X% abaixo do pico (0 = desativado)
    event_dedup_days: int = 3        # não operar o mesmo evento de notícia por X dias
    vol_target_atr_pct: float = 4.0  # ATR de referência p/ sizing (ativo mais volátil → posição menor)
    loss_streak_threshold: int = 3   # perdas consecutivas que ativam o circuit breaker anti-tilt
    loss_streak_factor: float = 0.5  # fator de redução do sizing durante o tilt


@dataclass
class DemoConfig:
    min_days: int = 30
    min_trades: int = 20
    min_return_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    must_beat_benchmark: bool = True  # exigir retorno ≥ buy-and-hold dos símbolos


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
    sentiment_enabled: bool = True
    reddit_subs: dict = field(default_factory=dict)  # {"crypto": [...], "stocks": [...]}
    calendar_enabled: bool = True
    reflection_every_days: int = 7

    def reddit_subs_for(self, market: str) -> List[str]:
        return list(self.reddit_subs.get(market, []))

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


def _candidates(filename: str) -> list[Path]:
    """Lugares onde procurar config.yaml/.env, em ordem de prioridade.

    Cobre tanto o modo dev (rodando da raiz do repo, ROOT correto) quanto o
    Docker, onde o pacote é instalado em site-packages (ROOT vira inútil) mas
    o WORKDIR é /app e o config.yaml está em /app/config.yaml (= cwd)."""
    cands: list[Path] = []
    if filename == "config.yaml" and os.environ.get("PHEBOS_CONFIG"):
        cands.append(Path(os.environ["PHEBOS_CONFIG"]))
    cands.append(Path.cwd() / filename)   # Docker: /app/<filename>
    cands.append(ROOT / filename)         # dev: raiz do repositório
    cands.append(DATA_DIR / filename)     # volume de dados
    return cands


def find_config() -> Path:
    """Caminho do config.yaml — primeiro candidato existente, ou cwd p/ erro claro."""
    for candidate in _candidates("config.yaml"):
        if candidate.exists():
            return candidate
    return Path.cwd() / "config.yaml"


def load_settings(path: Path | None = None) -> Settings:
    for env_file in _candidates(".env"):  # load_dotenv não erra se não existir
        if env_file.exists():
            load_dotenv(env_file)
            break
    load_dotenv(SECRETS_FILE, override=True)  # chaves do dashboard prevalecem
    config_path = path or find_config()
    raw = yaml.safe_load(config_path.read_text())

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
        sentiment_enabled=bool(raw.get("sentiment", {}).get("enabled", True)),
        reddit_subs=raw.get("sentiment", {}).get("reddit_subs", {}) or {},
        calendar_enabled=bool(raw.get("calendar", {}).get("enabled", True)),
        reflection_every_days=int(raw.get("reflection", {}).get("every_days", 7)),
    )


def kill_switch_active() -> bool:
    return KILL_FILE.exists()


# ── controle do ciclo pelo dashboard ────────────────────────────────
def get_runtime_interval(default: int) -> int:
    """Intervalo (min) salvo pelo dashboard, ou o padrão do config.yaml."""
    try:
        data = json.loads(RUNTIME_FILE.read_text())
        value = int(data.get("interval_minutes", default))
        return value if value >= 1 else default
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return default


def set_runtime_interval(minutes: int) -> int:
    """Salva o intervalo (mínimo 1 min). Escrita atômica. Retorna o valor salvo."""
    minutes = max(1, int(minutes))
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNTIME_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"interval_minutes": minutes}))
    tmp.replace(RUNTIME_FILE)
    return minutes


def request_run_now() -> None:
    """Dashboard pede um ciclo imediato; o agente consome no próximo check."""
    RUN_NOW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUN_NOW_FILE.touch()


def consume_run_now() -> bool:
    """Retorna True (e limpa o pedido) se havia um 'rodar agora' pendente."""
    if RUN_NOW_FILE.exists():
        try:
            RUN_NOW_FILE.unlink()
        except FileNotFoundError:
            pass
        return True
    return False
