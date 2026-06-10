# Phebos — Agente Autônomo de Trading com IA

Sistema autônomo que usa a **API do Gemini** (Google) para analisar o mercado
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
  → coleta manchetes de notícias via RSS (CoinDesk, Yahoo Finance, CNBC, ...)
  → PESQUISA: Gemini com Busca Google investiga as notícias das últimas horas
    (anúncios de governos, IPOs, descobertas, reação das redes sociais)
    e produz um briefing de inteligência de mercado
  → calcula indicadores técnicos (RSI, médias móveis, tendência de volume)
  → DECISÃO: Gemini recebe snapshot + indicadores + briefing e retorna uma
    decisão estruturada (JSON validado: ordens + justificativa), priorizando
    notícias fortes ainda não precificadas — como um gestor humano faria
  → motor de risco valida cada ordem (limites rígidos em código)
  → executa as ordens aprovadas via API da corretora/exchange
  → notifica cada trade no Telegram 📱
  → registra tudo no journal (SQLite): briefings, decisões, trades, patrimônio
```

```
src/phebos/
├── main.py          # ponto de entrada: loop do agente + comandos CLI
├── config.py        # carrega config.yaml + variáveis de ambiente
├── schemas.py       # modelos Pydantic (decisão da IA, ordens, snapshot)
├── news.py          # manchetes via RSS/Atom (parser próprio, sem deps extras)
├── indicators.py    # RSI, SMA, preço vs. média, tendência de volume
├── analyst.py       # 2 etapas: pesquisa (Busca Google) → decisão estruturada
├── notify.py        # notificações no Telegram (trades, vetos, erros)
├── risk.py          # motor de risco determinístico + kill switch
├── journal.py       # registro em SQLite (briefings, trades, patrimônio)
├── evaluation.py    # avalia o período demo e diz se está apto ao modo real
└── brokers/
    ├── base.py      # interface comum de corretora
    ├── binance.py   # Binance spot (testnet ou real)
    └── alpaca.py    # Alpaca (paper ou real)
```

### Inteligência de notícias

O agente reage a eventos do mundo real dentro do intervalo do ciclo
(`interval_minutes`). Exemplos do que o pesquisador captura:

- Governo anuncia compra de Bitcoin para reserva estratégica → tese de compra
  antes da alta consolidar.
- Empresa lança produto mal recebido pelo mercado/redes sociais → tese de venda.
- Descoberta relevante (ex.: nova bacia de petróleo) → tese de compra na ação.

> Custo/latência: o modelo padrão é o `gemini-2.5-flash` (muito barato) e a
> pesquisa usa o grounding com a Busca Google da própria API do Gemini.
> O sistema reage em minutos — rápido como um analista humano atento, mas não
> compete com robôs de alta frequência que reagem em milissegundos.

## Setup

1. **Python 3.10+** e dependências:

   ```bash
   pip install -e .
   ```

2. **Chaves de API** — copie `.env.example` para `.env` e preencha:

   - `GEMINI_API_KEY` — em https://aistudio.google.com/apikey
   - Telegram (opcional): token do bot via @BotFather + seu chat_id
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

## Notificações no Telegram

Com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env`, você recebe no celular:

- 🤖 quando o agente inicia (modo, mercados, intervalo)
- 🟢/🔴 cada compra/venda executada, com o valor e a justificativa da IA
- 🚫 ordens vetadas pelo motor de risco (e o motivo)
- ❗ erros no ciclo

Para desativar: `notifications.telegram: false` no `config.yaml`.

## Kill switch

Crie um arquivo chamado `KILL` na raiz do projeto e o agente para de enviar
ordens imediatamente no próximo ciclo (continua apenas observando).

```bash
touch KILL    # pausa as ordens
rm KILL       # retoma
```
