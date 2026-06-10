# Phebos — Agente Autônomo de Trading com IA

Sistema autônomo que usa a **API do Claude** (Anthropic) para analisar o mercado
e tomar decisões de compra/venda em dois mercados:

- **Cripto** via Binance (24/7) — com suporte à **testnet** (dinheiro fictício)
- **Ações dos EUA** via Alpaca — com suporte a **paper trading** (dinheiro fictício)

## ⚠️ Aviso importante

Trading automatizado envolve **risco real de perda de capital**. Um modelo de IA
analisando o mercado **não é garantia de lucro**. Este projeto:

- Nasce em **modo demo** (testnet/paper trading) por padrão.
- Possui uma **camada de risco determinística** (em código, não decidida pela IA)
  que limita tamanho de posição, perda diária e símbolos permitidos.
- Só opera com dinheiro real após um **período de avaliação** e uma
  **confirmação explícita** sua.

Use por sua conta e risco. Nada aqui é recomendação de investimento.

## Arquitetura

```
Loop (a cada N minutos)
  → coleta dados de mercado (candles, preços, posições, saldo)
  → chama a API do Claude (claude-opus-4-8) com os dados
  → Claude retorna decisão estruturada (JSON validado: ordens + justificativa)
  → motor de risco valida cada ordem (limites rígidos em código)
  → executa as ordens aprovadas via API da corretora/exchange
  → registra tudo no journal (SQLite): decisões, trades, evolução do patrimônio
```

```
src/phebos/
├── main.py          # ponto de entrada: loop do agente + comandos CLI
├── config.py        # carrega config.yaml + variáveis de ambiente
├── schemas.py       # modelos Pydantic (decisão da IA, ordens, snapshot)
├── analyst.py       # cliente da API do Claude — análise e decisão
├── risk.py          # motor de risco determinístico + kill switch
├── journal.py       # registro em SQLite (trades, decisões, patrimônio)
├── evaluation.py    # avalia o período demo e diz se está apto ao modo real
└── brokers/
    ├── base.py      # interface comum de corretora
    ├── binance.py   # Binance spot (testnet ou real)
    └── alpaca.py    # Alpaca (paper ou real)
```

## Setup

1. **Python 3.10+** e dependências:

   ```bash
   pip install -e .
   ```

2. **Chaves de API** — copie `.env.example` para `.env` e preencha:

   - `ANTHROPIC_API_KEY` — em https://platform.claude.com
   - Binance **testnet**: crie chaves em https://testnet.binance.vision (grátis)
   - Alpaca **paper**: crie conta em https://alpaca.markets (paper trading é grátis)

3. **Configuração** — ajuste `config.yaml` (símbolos, intervalo, limites de risco,
   critérios do período demo).

## Uso

```bash
# Roda o agente (modo demo por padrão)
python -m phebos.main run

# Executa um único ciclo de análise (útil para testar)
python -m phebos.main once

# Relatório do período demo: retorno, drawdown, taxa de acerto
# e veredito sobre os critérios de promoção ao modo real
python -m phebos.main evaluate
```

## Modo demo → modo real

1. O agente roda em demo pelo período definido em `config.yaml`
   (`demo.min_days`, padrão 30 dias).
2. `python -m phebos.main evaluate` mostra as métricas e diz se os critérios
   foram atingidos (retorno mínimo, drawdown máximo, nº mínimo de trades).
3. Para ir ao modo real (a qualquer momento, a decisão é sua):
   - mude `mode: live` no `config.yaml`;
   - preencha as chaves **reais** (`BINANCE_LIVE_*`, `ALPACA_LIVE_*`) no `.env`;
   - exporte `PHEBOS_CONFIRM_LIVE=EU_ACEITO_O_RISCO`.

   Sem a variável de confirmação, o sistema **recusa** iniciar em modo real.

## Kill switch

Crie um arquivo chamado `KILL` na raiz do projeto e o agente para de enviar
ordens imediatamente no próximo ciclo (continua apenas observando).

```bash
touch KILL    # pausa as ordens
rm KILL       # retoma
```
