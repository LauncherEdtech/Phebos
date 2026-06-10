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

Inteligência adicional que você recebe (use ativamente):
- CALENDÁRIO ECONÔMICO: eventos agendados (Fed, CPI, payroll, balanços).
  Antecipe: se um evento de alto impacto ocorre nas próximas 24h, prefira
  reduzir exposição ou aguardar — não abra posição grande às vésperas.
- SENTIMENTO SOCIAL (Reddit/StockTwits/Fear&Greed): reação do público em tempo
  real. Sentimento extremo (euforia/pânico) costuma ser contrário; mudança
  brusca de sentimento sobre um ativo específico é sinal antecipado.
- LIÇÕES APRENDIDAS: conclusões da sua própria auto-revisão de trades passados.
  Aplique-as — não repita os erros que você mesmo documentou.
- CALIBRAÇÃO DE CONFIANÇA: sua taxa de acerto histórica por nível de convicção.
  Se 'high' vem acertando pouco, seja mais criterioso ao declarar convicção alta.
- INDICADORES MULTI-TIMEFRAME: 1h (timing), 4h e diário (tendência maior) e o
  REGIME do mercado (alta/baixa/lateral). Não compre contra a tendência maior
  sem uma notícia forte que justifique a reversão.
"""

CALENDAR_SYSTEM = """\
Você é o assistente de agenda econômica do Phebos. Use a busca do Google para
listar os eventos econômicos AGENDADOS para os próximos 7 dias que podem mover
os mercados: decisões de juros (Fed/FOMC), CPI/PPI, payroll, PIB, e balanços
(earnings) das empresas monitoradas. Para cada evento: data (e hora se
disponível), o que é, e impacto esperado (alto/médio/baixo). Seja factual e
conciso; se não encontrar a agenda exata, diga o que é conhecido. Responda em
português, em lista.
"""

REFLECTION_SYSTEM = """\
Você é o revisor de performance do Phebos — o próprio agente analisando os
trades que ELE fez. Para cada trade fechado você recebe: tese de entrada,
convicção declarada, resultado (P&L) e motivo da saída. Também recebe a
calibração (acerto por nível de convicção).

Produza de 3 a 7 LIÇÕES acionáveis e específicas, em português. Exemplos do
formato esperado:
- "Comprei por notícia já precificada 2x (BTC reserva, NVDA chip) e perdi em
  ambas → verificar idade do evento antes de comprar."
- "Ordens 'high' acertaram 80%, 'low' apenas 20% → evitar operar com convicção
  baixa; esperar confirmação."
Aponte padrões, não casos isolados. Se os dados forem poucos, diga o que ainda
não dá para concluir. Termine com a lição mais importante em uma linha.
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

    # ── Calendário econômico (1 busca por dia, cacheada no journal) ─
    def calendar_briefing(self, all_symbols: list[str]) -> str:
        prompt = (
            f"Ativos monitorados: {', '.join(all_symbols)}.\n"
            "Liste os eventos econômicos agendados dos próximos 7 dias que podem "
            "mover esses ativos (macro EUA + earnings das empresas listadas)."
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=CALENDAR_SYSTEM,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return (response.text or "").strip() or "(calendário indisponível)"

    # ── Auto-reflexão: o agente revisa os próprios trades ──────────
    def reflect(self, closed_trades: list[dict], calibration: dict) -> str:
        lines = []
        for t in closed_trades:
            lines.append(
                f"- {t['ts'][:10]} {t['symbol']} | P&L {t['pnl_pct']:+.2f}% (${t['pnl_usd']:+.2f}) | "
                f"convicção: {t['confidence']} | saída: {t['reason']}\n"
                f"  Tese de entrada: {t['thesis']}"
            )
        prompt = (
            f"TRADES FECHADOS NO PERÍODO ({len(closed_trades)}):\n" + "\n".join(lines) +
            f"\n\nCALIBRAÇÃO POR CONVICÇÃO:\n{json.dumps(calibration, indent=2, ensure_ascii=False)}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=REFLECTION_SYSTEM),
        )
        return (response.text or "").strip() or "(reflexão não gerou conteúdo)"

    # ── Etapa 2: decisão estruturada ────────────────────────────────
    def decide(self, snapshot: MarketSnapshot, indicators: dict,
               news_briefing: str, risk_summary: str,
               context: dict | None = None) -> TradingDecision:
        """context: open_positions, recent_decisions, acted_events, lessons,
        calibration, calendar, sentiment (todos opcionais)."""
        ctx = context or {}
        memory = self._format_memory(ctx.get("open_positions") or [],
                                     ctx.get("recent_decisions") or [],
                                     ctx.get("acted_events") or [])
        extra_blocks = []
        if ctx.get("calendar"):
            extra_blocks.append(f"=== CALENDÁRIO ECONÔMICO (próximos dias) ===\n{ctx['calendar']}")
        if ctx.get("sentiment"):
            extra_blocks.append(f"=== SENTIMENTO SOCIAL ===\n{ctx['sentiment']}")
        if ctx.get("lessons"):
            extra_blocks.append(f"=== LIÇÕES APRENDIDAS (sua auto-revisão) ===\n{ctx['lessons']}")
        if ctx.get("calibration"):
            extra_blocks.append(
                "=== CALIBRAÇÃO DE CONFIANÇA (seu histórico real) ===\n"
                + json.dumps(ctx["calibration"], indent=2, ensure_ascii=False))

        user_prompt = (
            f"Limites de risco em vigor (informativo — aplicados em código):\n{risk_summary}\n\n"
            f"=== MEMÓRIA ===\n{memory}\n\n"
            + ("\n\n".join(extra_blocks) + "\n\n" if extra_blocks else "")
            + f"=== BRIEFING DE NOTÍCIAS (pesquisador) ===\n{news_briefing}\n\n"
            f"=== INDICADORES TÉCNICOS (1h/4h/1d + regime) ===\n"
            f"{json.dumps(indicators, indent=2, ensure_ascii=False)}\n\n"
            f"=== SNAPSHOT DO MERCADO ({snapshot.market}) ===\n"
            f"{json.dumps(self._snapshot_for_prompt(snapshot), indent=2, ensure_ascii=False)}"
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
    def _snapshot_for_prompt(snapshot: MarketSnapshot) -> dict:
        """Versão enxuta do snapshot para o prompt: os indicadores já resumem
        os timeframes maiores, então mandamos só os últimos 12 candles de 1h."""
        data = snapshot.model_dump()
        for sym in data.get("symbols", []):
            sym["candles"] = sym.get("candles", [])[-12:]
            sym.pop("candles_4h", None)
            sym.pop("candles_1d", None)
        return data

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
