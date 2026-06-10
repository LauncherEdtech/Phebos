"""Analista em duas etapas via API do Claude.

1. research() — Claude com a ferramenta de web search investiga as notícias
   das últimas horas sobre os ativos (anúncios, IPOs, eventos macro, reação
   das redes sociais) e produz um briefing de inteligência de mercado.
2. decide() — Claude recebe snapshot + indicadores técnicos + briefing e
   retorna uma decisão estruturada e validada (Pydantic).
"""

import json
import logging

import anthropic

from .schemas import MarketSnapshot, TradingDecision

log = logging.getLogger("phebos")

RESEARCH_SYSTEM = """\
Você é o pesquisador de mercado do Phebos, um agente autônomo de trading.
Sua missão é descobrir, ANTES que o mercado precifique por completo, eventos
que podem mover os ativos monitorados — como faria um analista humano
especializado lendo notícias o dia inteiro.

Use a busca na web para investigar as últimas 24-48 horas:
- Anúncios de governos e bancos centrais (ex.: reservas estratégicas, juros,
  regulação de cripto, tarifas comerciais).
- Notícias corporativas: resultados, IPOs, lançamentos de produto, fusões,
  descobertas (ex.: nova reserva de petróleo), recalls, escândalos.
- Reação do mercado e das redes sociais a lançamentos e eventos recentes.
- Eventos macro: inflação, emprego, conflitos, decisões do Fed.

As manchetes RSS fornecidas são pistas iniciais — verifique e aprofunde as
mais relevantes com buscas. Ignore ruído e clickbait.

Entregue um briefing objetivo em português com:
1. Eventos relevantes encontrados (com fonte e quando ocorreu).
2. Para cada ativo monitorado: implicação provável (alta/baixa/neutra) e por quê.
3. Avalie se o evento JÁ foi precificado (movimento antigo) ou ainda é recente.
Se não houver nada relevante, diga isso claramente — não invente sinal.
"""

DECISION_SYSTEM = """\
Você é o analista de investimentos do Phebos, um agente autônomo de trading.
A cada ciclo você recebe: snapshot do mercado (preços, candles de 1h, posições,
saldo), indicadores técnicos e um briefing de notícias produzido pelo seu
pesquisador. Decida como um gestor humano experiente:

- Notícias fortes e ainda não precificadas pesam mais que indicadores técnicos.
  Ex.: governo anuncia compra de Bitcoin para reserva → comprar BTC antes da
  alta consolidar; produto mal recebido pelo mercado/redes → reduzir posição.
- Indicadores técnicos servem de confirmação e de timing (RSI esticado,
  rompimento de média, volume crescendo).
- Seja seletivo: não operar é decisão válida e frequente. Só proponha ordens
  com tese clara baseada nos dados e no briefing recebidos.
- Considere as posições abertas: evite concentração e proponha venda quando a
  tese de uma posição se enfraquecer.
- Cada ordem precisa de justificativa objetiva citando o dado ou a notícia que
  a motivou. Use apenas símbolos presentes no snapshot.
- Suas ordens passam por um motor de risco que pode vetá-las; dimensione o
  valor proporcionalmente à sua confiança.
"""


class Analyst:
    def __init__(self, model: str, extra_instructions: str = "",
                 web_search: bool = True, max_web_searches: int = 6):
        self.client = anthropic.Anthropic()
        self.model = model
        self.extra_instructions = extra_instructions
        self.web_search = web_search
        self.max_web_searches = max_web_searches

    # ── Etapa 1: pesquisa de notícias com web search ────────────────
    def research(self, snapshot: MarketSnapshot, headlines_text: str) -> str:
        symbols = ", ".join(s.symbol for s in snapshot.symbols)
        user_prompt = (
            f"Mercado: {snapshot.market}. Ativos monitorados: {symbols}.\n\n"
            f"Manchetes recentes coletadas via RSS (pistas iniciais):\n{headlines_text}\n\n"
            "Produza o briefing de inteligência para este ciclo."
        )
        if not self.web_search:
            return f"(web search desativado — apenas manchetes RSS)\n{headlines_text}"

        messages = [{"role": "user", "content": user_prompt}]
        tools = [{
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": self.max_web_searches,
        }]
        for _ in range(5):  # proteção contra pause_turn em loop
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=RESEARCH_SYSTEM,
                tools=tools,
                messages=messages,
            )
            if response.stop_reason == "pause_turn":
                messages = messages + [{"role": "assistant", "content": response.content}]
                continue
            break
        briefing = "\n".join(b.text for b in response.content if b.type == "text")
        return briefing or "(pesquisa não retornou conteúdo neste ciclo)"

    # ── Etapa 2: decisão estruturada ────────────────────────────────
    def decide(self, snapshot: MarketSnapshot, indicators: dict,
               news_briefing: str, risk_summary: str) -> TradingDecision:
        user_prompt = (
            f"Limites de risco em vigor (informativo — aplicados em código):\n{risk_summary}\n\n"
            f"=== BRIEFING DE NOTÍCIAS (pesquisador) ===\n{news_briefing}\n\n"
            f"=== INDICADORES TÉCNICOS ===\n{json.dumps(indicators, indent=2, ensure_ascii=False)}\n\n"
            f"=== SNAPSHOT DO MERCADO ({snapshot.market}) ===\n"
            f"{snapshot.model_dump_json(indent=2)}"
        )
        if self.extra_instructions:
            user_prompt += f"\n\nInstruções adicionais do operador:\n{self.extra_instructions}"

        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=DECISION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=TradingDecision,
        )
        decision = response.parsed_output
        if decision is None:
            # Resposta fora do schema (ex.: refusal) — trata como "não operar"
            return TradingDecision(market_view="Análise indisponível neste ciclo.", orders=[])
        return decision
