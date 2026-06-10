# 📖 Guia completo do Phebos

> **Este arquivo é o manual oficial do sistema e é atualizado a cada alteração.**
> Última atualização: 2026-06-10 — correções de execução: caixa decrescente entre ordens do mesmo ciclo, motivo exato dos erros da Binance/Alpaca nos logs, tolerância a relógio dessincronizado (recvWindow + offset com retry) e rejeição de uma ordem não aborta as demais.

## O que é

O Phebos é um agente autônomo de trading que:

1. Monitora **cripto** (Binance) e **ações dos EUA** (Alpaca) em ciclos de
   15 minutos (configurável).
2. Lê **notícias** (RSS + pesquisa ativa com a Busca Google via API do Gemini)
   e calcula **indicadores técnicos** (RSI, médias móveis, volume).
3. Decide comprar/vender/esperar como um gestor humano — priorizando notícias
   fortes ainda não precificadas (ex.: governo compra BTC para reserva,
   empresa lança produto mal recebido pelo mercado).
4. Passa toda ordem por um **motor de risco em código** (a IA não tem a
   palavra final) e executa via API da corretora.
5. Protege cada posição com **stop-loss e take-profit automáticos** (e trailing
   stop opcional) — saídas disciplinadas em código, independentes da IA.
6. Tem **memória**: registra a tese de cada posição, relê as próprias decisões
   e **não opera o mesmo evento de notícia duas vezes** (dedupe).
7. Calcula **P&L realizado por posição** e métricas profissionais (taxa de
   acerto, fator de lucro, comparação com buy-and-hold).
8. **Antecipa eventos**: consulta o calendário econômico (Fed, CPI, payroll,
   earnings) uma vez por dia e reduz exposição às vésperas de evento forte.
9. **Aprende com os próprios erros**: a cada 7 dias revisa os trades fechados
   e gera lições que entram no prompt dos ciclos seguintes; acompanha a
   **calibração de confiança** (acerto real por nível de convicção declarado).
10. Lê o **sentimento social** (Reddit, StockTwits, Fear & Greed) para captar
    a reação do público antes de virar manchete.
11. **Dimensiona posições dinamicamente**: convicção × volatilidade (ATR) ×
    regime do mercado (alta/baixa/lateral, multi-timeframe 1h/4h/1d) — e corta
    o sizing pela metade após sequência de perdas (**anti-tilt**).
12. Registra tudo em SQLite, **avisa no Telegram** e exibe num **dashboard web**
    com aba de histórico completo (leituras, pensamentos, operações, reflexões).

⚠️ **Não há garantia de lucro.** O sistema nasce em modo demo (dinheiro
fictício) e só vai ao modo real com a sua confirmação explícita.

---

## 1. Pré-requisitos e chaves

| Chave | Onde criar | Custo |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | grátis (nível free) / centavos no pago |
| Binance testnet | https://testnet.binance.vision | grátis |
| Alpaca paper | https://alpaca.markets → API Keys (Paper) | grátis |
| Telegram (opcional) | @BotFather no Telegram | grátis |

**Telegram passo a passo:**
1. Fale com `@BotFather` → `/newbot` → copie o **token**.
2. Envie qualquer mensagem para o seu bot recém-criado.
3. Abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no navegador e
   copie o número em `"chat":{"id": ...}` → esse é o `TELEGRAM_CHAT_ID`.

Depois copie `.env.example` para `.env` e preencha tudo.

---

## 2. Instalação em 1 comando (recomendado) ⚡

Em qualquer Linux Ubuntu/Debian (VM, VPS ou WSL2 no Windows):

```bash
curl -fsSL https://raw.githubusercontent.com/LauncherEdtech/Phebos/main/setup.sh | bash
```

O instalador faz tudo sozinho:
1. instala Docker e Docker Compose (se faltarem);
2. clona/atualiza o repositório em `~/Phebos`;
3. pergunta as chaves interativamente (Gemini obrigatória; Binance/Alpaca
   opcionais — mercado sem chave é desativado automaticamente; Telegram opcional);
4. cria o `.env` com permissão restrita;
5. sobe agente + dashboard e mostra o status e os comandos úteis.

Pode rodar de novo quando quiser: ele atualiza o código e pergunta se você
quer reconfigurar as chaves (sem apagar nada por conta própria).

## 2.1 Rodando com Docker manualmente

Com Docker e Docker Compose instalados:

```bash
git clone <este-repositório> && cd Phebos
cp .env.example .env        # preencha as chaves
docker compose up -d --build
```

Isso sobe **dois serviços**:
- `agent` — o robô que analisa e opera, reiniciando sozinho se cair;
- `dashboard` — a interface web em **http://localhost:8000**.

Comandos úteis:

```bash
docker compose logs -f agent        # acompanhar o agente ao vivo
docker compose exec agent python -m phebos.main evaluate   # relatório demo
docker compose exec agent touch /app/data/KILL   # KILL SWITCH (pausa ordens)
docker compose exec agent rm /app/data/KILL      # retoma
docker compose restart agent        # aplicar mudanças do config.yaml
docker compose down                 # parar tudo (dados ficam no volume)
```

O banco (`phebos.db`) e o kill switch vivem no volume `phebos-data` — derrubar
e subir os containers **não apaga o histórico**.

## 3. Rodando sem Docker (local)

```bash
pip install -e .
cp .env.example .env                 # preencha as chaves
python -m phebos.main once           # 1 ciclo de teste
python -m phebos.main run            # loop contínuo
python -m phebos.main dashboard      # dashboard em http://localhost:8000 (outro terminal)
python -m phebos.main evaluate       # relatório do período demo
```

---

## 4. O dashboard

Abra **http://localhost:8000**. Ele mostra:

- **Cartões**: patrimônio, retorno do período, **alfa vs buy-and-hold**,
  **P&L realizado**, **taxa de acerto**, **fator de lucro**, drawdown,
  trades executados, ordens vetadas, dias rodando.
- **Gráfico** da evolução do patrimônio (uma linha por mercado).
- **Critérios demo → real** com checkmarks de progresso.
- **Posições abertas**: valor, preço médio, P&L ao vivo e a **tese** que
  motivou cada compra.
- **Posições encerradas**: P&L realizado de cada saída e o motivo
  (🛑 stop-loss, 🎯 take-profit, 📉 trailing, 🧠 decisão da IA).
- **Operações**: cada compra/venda com valor, status (executada/vetada) e a
  justificativa da IA — ou o motivo do veto do motor de risco.
- **Decisões da IA**: a leitura de mercado de cada ciclo.
- **Briefings de notícias**: o relatório completo do pesquisador a cada ciclo
  (clique para expandir).

- **Calibração de confiança**: acerto real por convicção declarada pela IA.
- **Lições aprendidas**: a auto-reflexão mais recente do agente.
- **Aba "Histórico do bot"**: linha do tempo completa — 🔎 leituras de mercado,
  🧠 pensamentos, 💱 operações, 🏁 resultados e 📚 reflexões, com filtros.
- **Aba "Logs ao vivo"**: terminal com os logs do agente (filtros por
  Info/Avisos/Erros), atualizado a cada 10s — sem precisar de SSH.
- **Aba "Conexões"**: defina as chaves de API pelo navegador e clique em
  "Testar conexões" — 1 chamada barata por serviço confirma se cada chave
  funciona (o teste do Telegram envia uma mensagem real). As chaves vão para
  `secrets.env` (permissão 600, prioridade sobre o `.env`) e o **agente
  recarrega sozinho no próximo ciclo**, sem reiniciar container. A tela nunca
  mostra a chave completa (só prévia mascarada) e chaves de dinheiro REAL não
  podem ser definidas por ali — apenas via `.env`, por segurança.
- **Barra de controle** (topo da Visão geral): botão **"▶ Rodar ciclo agora"**
  dispara um ciclo na hora, sem esperar o intervalo; e o campo **"Cadência do
  ciclo"** ajusta o intervalo (em minutos) — o agente aplica no próximo passo,
  sem reiniciar. O intervalo vale a partir da próxima espera; intervalos curtos
  (< 5 min) consomem mais cota da API.

Visual em branco/preto/dourado. Atualiza sozinho a cada 60 segundos.
A porta muda com `PHEBOS_DASHBOARD_PORT`.

> 🔒 O dashboard não tem login. Na sua máquina, tudo bem. Num servidor,
> não exponha a porta 8000 ao mundo: acesse via túnel SSH
> (`ssh -L 8000:localhost:8000 usuario@servidor`) ou coloque atrás de um
> proxy com senha. No `docker-compose.yml`, troque `"8000:8000"` por
> `"127.0.0.1:8000:8000"` para garantir acesso só local.

---

## 5. Onde hospedar (do mais barato ao mais caro)

O agente precisa rodar 24/7, então plataformas serverless não servem bem.
Opções na prática:

| Opção | Custo/mês | Observações |
|---|---|---|
| **Seu próprio PC/notebook ligado** | R$ ~0 | Ótimo para o período demo. Use Docker; se desligar, perde ciclos (sem prejuízo: o robô só perde oportunidades). |
| **Oracle Cloud Always Free** ⭐ | **R$ 0** | VM ARM grátis para sempre (até 4 vCPU/24 GB). Melhor custo-benefício, exige cartão no cadastro. |
| **VPS barata (Hetzner, Contabo, DigitalOcean)** | US$ 4–6 | Simples e confiável. Hetzner CX22 (~€4) sobra para o Phebos. |
| **Fly.io / Railway** | US$ ~5 | Deploy fácil via Dockerfile, mas o modelo de cobrança flutua com uso. |

**Receita para qualquer VPS Ubuntu:**

```bash
# no servidor
curl -fsSL https://get.docker.com | sh
git clone <repositório> && cd Phebos
cp .env.example .env && nano .env          # preencha as chaves
docker compose up -d --build
# dashboard via túnel SSH a partir do seu PC:
ssh -L 8000:localhost:8000 usuario@ip-do-servidor
```

**Custos de API para operar** (independente da hospedagem):
- Gemini 2.5 Flash: centavos de dólar/dia nesse volume de chamadas.
- Grounding com Busca Google: cobrado por consulta no plano pago
  (há cota gratuita diária no nível free) — preços em https://ai.google.dev/pricing.
  Para zerar: `analyst.web_search: false` no `config.yaml` (decide só com RSS + indicadores).
- Binance testnet, Alpaca paper e Telegram: grátis.

---

## 6. Configuração (`config.yaml`)

| Chave | O que faz |
|---|---|
| `mode` | `demo` (fictício) ou `live` (real — exige confirmação, ver §7) |
| `interval_minutes` | Intervalo entre ciclos de análise |
| `markets.crypto.symbols` | Pares da Binance (ex.: `BTCUSDT`) |
| `markets.stocks.symbols` | Tickers da Alpaca (ex.: `AAPL`; `PBR` = Petrobras ADR) |
| `risk.max_pct_per_trade` | % máximo do patrimônio por ordem |
| `risk.max_open_positions` | Posições abertas simultâneas por mercado |
| `risk.max_daily_loss_pct` | Perda diária que congela novas ordens até o dia seguinte |
| `risk.stop_loss_pct` | Venda automática se a posição cair X% do preço médio (padrão 8) |
| `risk.take_profit_pct` | Venda automática se a posição subir X% do preço médio (padrão 15) |
| `risk.trailing_stop_pct` | Venda se cair X% abaixo do pico desde a entrada (0 = desligado) |
| `risk.event_dedup_days` | Janela em que o mesmo evento de notícia não é re-operado (padrão 3) |
| `risk.vol_target_atr_pct` | ATR de referência do sizing: ativo mais volátil → posição menor (padrão 4) |
| `risk.loss_streak_threshold` | Perdas seguidas que ativam o anti-tilt (padrão 3) |
| `risk.loss_streak_factor` | Fator de corte do sizing durante o tilt (padrão 0.5) |
| `sentiment.enabled` | Liga/desliga Reddit + StockTwits + Fear & Greed |
| `sentiment.reddit_subs` | Subreddits monitorados por mercado |
| `calendar.enabled` | Liga/desliga o calendário econômico (1 busca/dia, cacheada) |
| `reflection.every_days` | Frequência da auto-reflexão (padrão 7 dias) |
| `demo.*` | Critérios do período demo (dias, trades, retorno, drawdown) |
| `demo.must_beat_benchmark` | Exige retorno ≥ buy-and-hold dos símbolos para aprovar o demo |
| `news.rss_feeds` | Feeds RSS por mercado |
| `analyst.model` | `gemini-2.5-flash` (barato) ou `gemini-2.5-pro` (mais capaz) |
| `analyst.web_search` | Pesquisa ativa com Busca Google (true/false) |
| `analyst.extra_instructions` | Instrução extra sua para o analista (estilo, viés) |
| `notifications.telegram` | Liga/desliga avisos no Telegram |

Depois de editar, reinicie: `docker compose restart` (ou Ctrl+C e rodar de novo).

---

## 7. Do demo ao dinheiro real

1. Deixe rodar em demo pelo período configurado (padrão: 30 dias, 20+ trades).
2. Acompanhe pelo dashboard ou rode `evaluate` — os critérios aparecem com ✅.
3. Quando decidir promover (mesmo sem os critérios, a decisão é sua):
   - `mode: live` no `config.yaml`;
   - chaves reais `BINANCE_LIVE_*` / `ALPACA_LIVE_*` no `.env`;
   - `PHEBOS_CONFIRM_LIVE=EU_ACEITO_O_RISCO` no `.env`.
4. Reinicie. Sem a variável de confirmação o sistema **recusa** iniciar em live.

💡 Comece o modo real com pouco capital e limites de risco apertados.

## 8. Kill switch (botão de pânico)

- **Local**: `touch KILL` na raiz do projeto → nenhuma ordem nova é enviada
  (o agente continua observando). `rm KILL` retoma.
- **Docker**: `docker compose exec agent touch /app/data/KILL` / `rm /app/data/KILL`.

> ⚠️ O kill switch bloqueia **todas** as ordens — inclusive os stop-loss
> automáticos. Se ativá-lo com posições abertas, elas ficam desprotegidas:
> avalie fechá-las manualmente na corretora.

## 8.1 Como funciona a disciplina de saída

A cada ciclo, ANTES de consultar a IA, o motor de risco verifica cada posição
aberta contra o preço atual:

1. caiu `stop_loss_pct`% abaixo do preço médio → **vende tudo** (🛑);
2. subiu `take_profit_pct`% acima do preço médio → **vende tudo** (🎯);
3. (opcional) caiu `trailing_stop_pct`% abaixo do **pico** desde a entrada → vende (📉).

Essas vendas não passam pela IA nem pelo congelamento de perda diária —
reduzir risco é sempre permitido. Cada saída realiza o P&L (registrado na
tabela `realized` e no dashboard) e avisa no Telegram.

A IA é instruída a vender quando a **tese** da posição enfraquecer — as
proteções mecânicas cuidam do resto.

## 8.2 Rodando os testes

A suíte cobre indicadores, motor de risco (sizing, vetos, saídas, anti-tilt),
contabilidade de posições, dedupe, reflexão, calendário, sentimento, brokers
(com APIs simuladas), dashboard e o fluxo completo do agente:

```bash
pip install pytest
python -m pytest tests/ -q
```

## 9. Solução de problemas

| Sintoma | Causa provável / solução |
|---|---|
| `Credenciais ... ausentes no .env` | Preencha as chaves do mercado habilitado, ou desabilite o mercado no `config.yaml`. |
| `Modo LIVE bloqueado` | Falta `PHEBOS_CONFIRM_LIVE=EU_ACEITO_O_RISCO` no ambiente. |
| `feed RSS indisponível (...)` | Feed fora do ar ou rede bloqueada — o ciclo continua sem ele. |
| Dashboard vazio | O agente ainda não rodou nenhum ciclo (`once`/`run`), ou os serviços não compartilham o mesmo volume/banco. |
| `No such file or directory: '.../config.yaml'` | O pacote instalado não achava o config. Corrigido nesta versão (busca em PHEBOS_CONFIG/cwd/repo). Atualize: `git pull && docker compose up -d --build`. |
| Nenhum log e nenhuma request de API | Chave do Gemini ausente/errada na inicialização. Desde esta versão o agente não morre mais: ele loga o erro na aba **Logs** e tenta de novo a cada 30s — salve a chave correta na aba **Conexões** que ele se recupera sozinho. Em versões antigas, atualize: `git pull && docker compose up -d --build`. |
| Erro 401/403 da Binance/Alpaca | Chave errada para o modo: testnet ≠ live; paper ≠ live. |
| Telegram mudo | Token/chat_id errados, ou você não mandou a 1ª mensagem para o bot. |
| Mercado de ações "fechado" | Normal: NYSE opera ~9h30–16h de NY em dias úteis. Cripto segue 24/7. |

## 10. Mapa do código

```
src/phebos/
├── main.py          # CLI: run | once | evaluate | dashboard
├── config.py        # config.yaml + .env + trava do modo live
├── schemas.py       # modelos Pydantic (decisão, ordens, snapshot)
├── news.py          # manchetes RSS/Atom (parser próprio)
├── indicators.py    # RSI, SMA, preço vs. média, tendência de volume
├── analyst.py       # Gemini: pesquisa (Busca Google) → decisão estruturada
├── notify.py        # Telegram (início, trades, vetos, erros)
├── risk.py          # motor de risco determinístico + kill switch
├── journal.py       # SQLite: decisões, trades, briefings, patrimônio
├── evaluation.py    # métricas do demo e critérios de promoção
├── dashboard.py     # API FastAPI + página web (web/index.html)
└── brokers/         # binance.py (testnet/real) e alpaca.py (paper/real)
```
