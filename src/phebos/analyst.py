"""Analista em duas etapas via API do Gemini (Google).

1. research() — Gemini com grounding na Busca Google investiga as notícias
   das últimas horas sobre os ativos (anúncios, IPOs, eventos macro, reação
   das redes sociais) e produz um briefing de inteligência de mercado.
2. decide() — Gemini recebe snapshot + indicadores técnicos + briefing e
   retorna uma decisão estruturada validada pelo schema Pydantic.

(As duas etapas são separadas porque a API não permite combinar busca do
Google com saída JSON estruturada na mesma chamada.)
"""

import json
import logging

from google import genai
from google.genai import types

from .schemas import MarketSnapshot, TradingDecision

log = logging.getLogger("phebos")

RESEARCH_SYSTEM = """\
Você é o pesquisador de mercado do Phebos, um agente autônomo de trading.
Sua missão é descobrir, ANTES que o mercado precifique por completo, eventos
que podem mover os ativos monitorados — como faria um analista humano
especializado lendo notícias o dia inteiro.

Use a busca do Google para investigar as últimas 24-48 horas:
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

Você também recebe a sua MEMÓRIA:
- POSIÇÕES ABERTAS com a tese que motivou cada uma e o P&L atual. Reavalie
  cada tese: se a notícia/condição que justificou a posição se enfraqueceu ou
  foi invalidada, proponha a venda. Se segue válida, mantenha.
- SUAS DECISÕES RECENTES: mantenha coerência — não inverta a posição a cada
  ciclo sem um fato novo que justifique.
- EVENTOS JÁ OPERADOS: você JÁ reagiu a esses eventos de notícia. NÃO proponha
  nova ordem motivada pelo mesmo evento (será vetada). Para cada ordem
  motivada por notícia, preencha event_key com um identificador curto e
  estável do evento em kebab-case (ex.: 'eua-reserva-estrategica-btc');
  use o MESMO identificador que aparece na lista se for o mesmo evento.
  Ordens puramente técnicas (sem notícia) levam event_key = null.

O sistema tem stop-loss e take-profit automáticos em código — você não precisa
vender só para proteger lucro/limitar perda pequena; venda quando a TESE mudar.
"""


class Analyst:
    def __init__(self, model: str, extra_instructions: str = "", web_search: bool = True):
        # Lê GEMINI_API_KEY (ou GOOGLE_API_KEY) do ambiente
        self.client = genai.Client()
        self.model = model
        self.extra_instructions = extra_instructions
        self.web_search = web_search

    # ── Etapa 1: pesquisa de notícias com busca do Google ───────────
    def research(self, snapshot: MarketSnapshot, headlines_text: str) -> str:
        symbols = ", ".join(s.symbol for s in snapshot.symbols)
        user_prompt = (
            f"Mercado: {snapshot.market}. Ativos monitorados: {symbols}.\n\n"
            f"Manchetes recentes coletadas via RSS (pistas iniciais):\n{headlines_text}\n\n"
            "Produza o briefing de inteligência para este ciclo."
        )
        if not self.web_search:
            return f"(busca na web desativada — apenas manchetes RSS)\n{headlines_text}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=RESEARCH_SYSTEM,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return (response.text or "").strip() or "(pesquisa não retornou conteúdo neste ciclo)"

    # ── Etapa 2: decisão estruturada ────────────────────────────────
    def decide(self, snapshot: MarketSnapshot, indicators: dict,
               news_briefing: str, risk_summary: str,
               open_positions: list[dict] | None = None,
               recent_decisions: list[dict] | None = None,
               acted_events: list[dict] | None = None) -> TradingDecision:
        memory = self._format_memory(open_positions or [], recent_decisions or [],
                                     acted_events or [])
        user_prompt = (
            f"Limites de risco em vigor (informativo — aplicados em código):\n{risk_summary}\n\n"
            f"=== MEMÓRIA ===\n{memory}\n\n"
            f"=== BRIEFING DE NOTÍCIAS (pesquisador) ===\n{news_briefing}\n\n"
            f"=== INDICADORES TÉCNICOS ===\n{json.dumps(indicators, indent=2, ensure_ascii=False)}\n\n"
            f"=== SNAPSHOT DO MERCADO ({snapshot.market}) ===\n"
            f"{snapshot.model_dump_json(indent=2)}"
        )
        if self.extra_instructions:
            user_prompt += f"\n\nInstruções adicionais do operador:\n{self.extra_instructions}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=DECISION_SYSTEM,
                response_mime_type="application/json",
                response_schema=TradingDecision,
            ),
        )
        decision = response.parsed
        if not isinstance(decision, TradingDecision):
            # Resposta fora do schema (ex.: bloqueio de segurança) → não operar
            log.warning("decisão fora do schema — tratando como 'não operar'")
            return TradingDecision(market_view="Análise indisponível neste ciclo.", orders=[])
        return decision

    @staticmethod
    def _format_memory(open_positions: list[dict], recent_decisions: list[dict],
                       acted_events: list[dict]) -> str:
        parts = ["POSIÇÕES ABERTAS (com a tese de cada uma):"]
        if open_positions:
            for p in open_positions:
                parts.append(
                    f"- {p['symbol']}: ${p['notional_usd']:.2f} | preço médio ${p['avg_price']:.4f} | "
                    f"P&L atual {p['pnl_pct']:+.2f}% | aberta em {p['opened_at'][:16]}\n"
                    f"  Tese: {p['thesis']}"
                )
        else:
            parts.append("- (nenhuma)")

        parts.append("\nSUAS DECISÕES RECENTES (mais nova primeiro):")
        if recent_decisions:
            for d in recent_decisions:
                parts.append(f"- {d['ts'][:16]}: {d['market_view']} ({d['orders_proposed']} ordens)")
        else:
            parts.append("- (nenhuma)")

        parts.append("\nEVENTOS JÁ OPERADOS (NÃO operar de novo):")
        if acted_events:
            for e in acted_events:
                parts.append(f"- event_key='{e['event_key']}' → {e['side']} {e['symbol']} em {e['ts'][:16]}")
        else:
            parts.append("- (nenhum)")
        return "\n".join(parts)
