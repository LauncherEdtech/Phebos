"""Analista: chama a API do Claude e retorna uma decisão estruturada e validada."""

import anthropic

from .schemas import MarketSnapshot, TradingDecision

SYSTEM_PROMPT = """\
Você é o analista de investimentos do Phebos, um agente autônomo de trading.
A cada ciclo você recebe um snapshot do mercado (preços, candles de 1h das
últimas 24h, posições abertas, saldo e patrimônio) e decide se deve operar.

Diretrizes:
- Seja seletivo: não operar é uma decisão válida e frequente. Só proponha
  ordens quando houver um sinal claro nos dados fornecidos.
- Considere as posições já abertas: evite concentração num mesmo ativo e
  proponha vendas quando a tese de uma posição se enfraquecer.
- Cada ordem deve ter justificativa objetiva baseada nos dados do snapshot,
  nunca em informação que você não recebeu.
- Suas ordens passam por um motor de risco que pode vetá-las; proponha
  tamanhos proporcionais à sua confiança.
- Use apenas os símbolos presentes no snapshot.
"""


class Analyst:
    def __init__(self, model: str, extra_instructions: str = ""):
        self.client = anthropic.Anthropic()
        self.model = model
        self.extra_instructions = extra_instructions

    def decide(self, snapshot: MarketSnapshot, risk_summary: str) -> TradingDecision:
        user_prompt = (
            f"Limites de risco em vigor (informativo — aplicados em código):\n{risk_summary}\n\n"
            f"Snapshot do mercado ({snapshot.market}):\n{snapshot.model_dump_json(indent=2)}"
        )
        if self.extra_instructions:
            user_prompt += f"\n\nInstruções adicionais do operador:\n{self.extra_instructions}"

        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=TradingDecision,
        )
        decision = response.parsed_output
        if decision is None:
            # Resposta fora do schema (ex.: refusal) — trata como "não operar"
            return TradingDecision(market_view="Análise indisponível neste ciclo.", orders=[])
        return decision
