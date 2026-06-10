"""Sentimento social: Reddit, StockTwits e índice Fear & Greed (sem chaves).

Capta a reação do público a eventos ANTES dela virar manchete — o caso
"Ferrari lança carro elétrico e as redes não gostaram".
Toda fonte é opcional: falhas nunca derrubam o ciclo.
"""

import logging
from typing import List

import requests

log = logging.getLogger("phebos")

_HEADERS = {"User-Agent": "Phebos/0.1 (agente de análise de mercado)"}
_TIMEOUT = 10


def fetch_reddit_hot(subreddits: List[str], limit: int = 10) -> List[dict]:
    """Títulos mais quentes de cada subreddit, com score (proxy de atenção)."""
    posts: List[dict] = []
    for sub in subreddits:
        try:
            data = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
                headers=_HEADERS, timeout=_TIMEOUT,
            ).json()
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = (post.get("title") or "").strip()
                if title and not post.get("stickied"):
                    posts.append({"sub": sub, "title": title,
                                  "score": post.get("score", 0),
                                  "comments": post.get("num_comments", 0)})
        except Exception as exc:
            log.warning("reddit r/%s indisponível: %s", sub, exc)
    return posts


def fetch_stocktwits(symbol: str, limit: int = 15) -> dict | None:
    """Mensagens recentes do StockTwits com contagem bullish/bearish.

    Símbolos cripto usam sufixo .X (BTCUSDT → BTC.X); ações usam o ticker puro.
    """
    st_symbol = symbol
    if symbol.endswith("USDT"):
        st_symbol = symbol[:-4] + ".X"
    try:
        data = requests.get(
            f"https://api.stocktwits.com/api/2/streams/symbol/{st_symbol}.json",
            headers=_HEADERS, timeout=_TIMEOUT,
        ).json()
        messages = data.get("messages", [])[:limit]
        if not messages:
            return None
        bullish = bearish = 0
        samples: List[str] = []
        for message in messages:
            sentiment = ((message.get("entities") or {}).get("sentiment") or {}).get("basic")
            if sentiment == "Bullish":
                bullish += 1
            elif sentiment == "Bearish":
                bearish += 1
            body = (message.get("body") or "").strip().replace("\n", " ")
            if body and len(samples) < 3:
                samples.append(body[:160])
        return {"symbol": symbol, "messages": len(messages),
                "bullish": bullish, "bearish": bearish, "samples": samples}
    except Exception as exc:
        log.warning("stocktwits %s indisponível: %s", st_symbol, exc)
        return None


def fetch_fear_greed() -> dict | None:
    """Índice Fear & Greed do mercado cripto (alternative.me, gratuito)."""
    try:
        data = requests.get("https://api.alternative.me/fng/?limit=1",
                            headers=_HEADERS, timeout=_TIMEOUT).json()
        item = (data.get("data") or [None])[0]
        if not item:
            return None
        return {"value": int(item["value"]), "label": item["value_classification"]}
    except Exception as exc:
        log.warning("fear&greed indisponível: %s", exc)
        return None


def collect(market: str, symbols: List[str], reddit_subs: List[str]) -> str:
    """Bloco de texto com o sentimento social do mercado, para o prompt."""
    parts: List[str] = []

    if market == "crypto":
        fng = fetch_fear_greed()
        if fng:
            parts.append(f"Índice Fear & Greed (cripto): {fng['value']}/100 — {fng['label']}")

    posts = fetch_reddit_hot(reddit_subs)
    if posts:
        top = sorted(posts, key=lambda p: p["score"], reverse=True)[:8]
        parts.append("Reddit (posts quentes, score = atenção):")
        parts.extend(f"- [r/{p['sub']} | {p['score']}↑ {p['comments']}💬] {p['title']}" for p in top)

    st_lines: List[str] = []
    for symbol in symbols:
        st = fetch_stocktwits(symbol)
        if st and (st["bullish"] or st["bearish"]):
            st_lines.append(
                f"- {symbol}: {st['bullish']}🐂 vs {st['bearish']}🐻 "
                f"(de {st['messages']} mensagens)"
            )
    if st_lines:
        parts.append("StockTwits (sentimento declarado dos traders):")
        parts.extend(st_lines)

    return "\n".join(parts) if parts else "(sem dados de sentimento neste ciclo)"
