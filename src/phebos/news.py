"""Coleta de manchetes via RSS/Atom — sinal de notícias rápido e gratuito.

Parser próprio com xml.etree (stdlib): sem dependências externas frágeis.
As manchetes servem de "pistas" para o pesquisador (Claude + web search)
aprofundar, e vão também direto no prompt de decisão.
"""

import logging
import xml.etree.ElementTree as ET
from typing import List

import requests

log = logging.getLogger("phebos")

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_feed(content: bytes) -> tuple[str, List[dict]]:
    root = ET.fromstring(content)
    entries: List[dict] = []

    if root.tag == f"{_ATOM_NS}feed":  # Atom
        source = (root.findtext(f"{_ATOM_NS}title") or "").strip()
        for entry in root.findall(f"{_ATOM_NS}entry"):
            entries.append({
                "title": (entry.findtext(f"{_ATOM_NS}title") or "").strip(),
                "published": (entry.findtext(f"{_ATOM_NS}published")
                              or entry.findtext(f"{_ATOM_NS}updated") or "").strip(),
            })
        return source, entries

    channel = root.find("channel")  # RSS 2.0
    if channel is None:
        return "", []
    source = (channel.findtext("title") or "").strip()
    for item in channel.findall("item"):
        entries.append({
            "title": (item.findtext("title") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
        })
    return source, entries


def fetch_headlines(feeds: List[str], limit_per_feed: int = 8) -> List[dict]:
    headlines: List[dict] = []
    for url in feeds:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Phebos/0.1"})
            resp.raise_for_status()
            source, entries = _parse_feed(resp.content)
            for entry in entries[:limit_per_feed]:
                if not entry["title"]:
                    continue
                headlines.append({"source": source or url, **entry})
        except Exception as exc:  # feed fora do ar não pode derrubar o ciclo
            log.warning("feed RSS indisponível (%s): %s", url, exc)
    return headlines


def format_headlines(headlines: List[dict]) -> str:
    if not headlines:
        return "(nenhuma manchete disponível neste ciclo)"
    return "\n".join(f"- [{h['source']}] {h['title']} ({h['published']})" for h in headlines)
