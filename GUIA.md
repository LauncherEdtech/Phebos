# 📖 Guia completo do PixZap

> **Este arquivo é o manual oficial do sistema e é atualizado a cada alteração.**
> Última atualização: 2026-07-02 (2ª edição do dia) — multi-idiomas (pt/en/es),
> painel do vendedor via link mágico (comando `painel`), painel do admin
> (`/admin`), landing page (`site/index.html`) e plano de negócios
> (`docs/plano-de-negocios.md`).

## O que é

O PixZap elimina a conferência manual de Pix de quem vende pelo WhatsApp:

1. O vendedor manda `cobrar 150,00 João pedido 12` no próprio WhatsApp.
2. O bot cria a cobrança no PSP (provedor de pagamento) e devolve o
   **Pix copia-e-cola** para encaminhar ao cliente.
3. Quando o dinheiro **cai de verdade**, o PSP chama nosso webhook
   autenticado e o bot confirma no chat: "✅ Pix de R$ 150,00 confirmado".
4. Screenshot de comprovante deixa de valer — o que confirma é o webhook.
   Isso mata o **golpe do comprovante falso** na origem.

A origem do produto está documentada em
[docs/analise-mercado-dores-globais.md](docs/analise-mercado-dores-globais.md)
(pesquisa de mercado com verificação adversarial, jul/2026).

## Comandos do bot (no WhatsApp)

| Comando | O que faz |
|---|---|
| `cobrar 150,00 João pedido 12` | cria cobrança e devolve o copia-e-cola |
| `pendentes` | lista cobranças aguardando pagamento + total a receber |
| `hoje` | resumo do dia: pagas, total recebido, pendentes |
| `cancelar 12` | cancela a cobrança #12 (se ainda pendente) |
| `painel` | link mágico (24 h) para o painel web de métricas |
| `ajuda` | mostra o menu |

Valores aceitos: `150`, `150,50`, `R$ 1.500,50`.

## Idiomas

As respostas do bot e o painel saem no idioma do `language` do config.yaml
(`pt` padrão, `en`, `es`) — catálogo em `src/pixzap/i18n.py`; os comandos são
os mesmos em todos os idiomas. Idioma desconhecido cai no pt-BR.

## Painéis web

- **Vendedor** — comando `painel` no chat gera um link assinado
  (`/painel?token=...`, HMAC com validade de 24 h, segredo em
  `PIXZAP_DASHBOARD_SECRET` ou gerado e persistido em `dashboard.secret`).
  Mostra: recebido hoje/7 dias, pendências, cobranças recentes e pagamentos
  com o veredito da conciliação. Requer `public_url` no config.yaml.
- **Admin** — `/admin?token=<PIXZAP_ADMIN_TOKEN>`: todas as cobranças e
  webhooks recebidos, com destaque para alertas (valor divergente / Pix sem
  cobrança). Sem o env definido, a rota responde 403 sempre.

## Regras de segurança (nunca enfraquecer sem pedido explícito)

1. **Só o webhook autenticado do PSP confirma pagamento.** Sem token/assinatura
   válida → HTTP 401 e nada muda. Nunca confirmar por mensagem no chat.
2. **Conciliação exata ao centavo** (`matching.py`): valor divergente não
   quita a cobrança — alerta o vendedor e a cobrança segue pendente.
3. **Idempotência**: o mesmo txid confirmado duas vezes é webhook repetido —
   ignorado em silêncio (índice único no SQLite garante).
4. **Allowlist** (`seller_numbers` no config.yaml): mensagem de número não
   autorizado é ignorada sem resposta.
5. **Dinheiro é sempre `int` em centavos** — nunca float.
6. **Segredos só em variáveis de ambiente** (.env), nunca no config.yaml.

## Instalação (desenvolvimento)

```bash
pip install -e . && pip install pytest httpx
cp .env.example .env       # pode deixar vazio para usar os fakes
python -m pytest tests     # 19 testes, tudo com fakes (sem rede externa)
python -m pixzap.main      # http://localhost:8000
```

Com `provider: fake` (padrão do config.yaml) dá para simular tudo localmente:

```bash
# vendedor manda comando (simula o webhook do WhatsApp)
curl -X POST localhost:8000/webhook/whatsapp \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"from":"5511999998888","text":"cobrar 150 João"}]}'

# o Pix "cai" (simula o webhook do PSP fake; token padrão: "teste")
curl -X POST localhost:8000/webhook/psp \
  -H 'Content-Type: application/json' -H 'x-fake-token: teste' \
  -d '{"event":"PAYMENT_RECEIVED","txid":"FAKE00000001","amount_cents":15000,"payer_name":"Maria"}'
```

(lembre de colocar `5511999998888` em `seller_numbers` no config.yaml)

## Configuração

`config.yaml` (nada de segredo aqui):

```yaml
seller_numbers: ["5511999998888"]   # quem pode dar comandos
timezone: America/Sao_Paulo
port: 8000
whatsapp:
  provider: cloud                    # fake | cloud
  phone_number_id: "1234567890"
psp:
  provider: asaas                    # fake | asaas | mercadopago
  asaas_sandbox: true
  asaas_pix_key: "sua-chave-pix"
```

`.env` (segredos — ver `.env.example`): `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_VERIFY_TOKEN`, `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN`,
`MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`.

## Provedores

### WhatsApp
- **fake** — desenvolvimento/testes (guarda mensagens em memória).
- **cloud** — WhatsApp Business Cloud API oficial (Meta). Decisão de produto:
  não usamos bibliotecas não oficiais (risco de banimento do número).
  Setup: https://developers.facebook.com → app → WhatsApp → API Setup.
  Webhook: `GET/POST /webhook/whatsapp` (o GET é o handshake `hub.challenge`).

### PSP (pagamento)
- **fake** — desenvolvimento/testes; webhook autenticado pelo header
  `x-fake-token`.
- **asaas** (beta) — QR estático com valor via `/v3/pix/qrCodes/static`;
  webhook `PAYMENT_RECEIVED` autenticado pelo header `asaas-access-token`,
  que deve ser igual ao `ASAAS_WEBHOOK_TOKEN`.
- **mercadopago** (beta) — pagamento Pix via `/v1/payments`; o webhook só
  traz o id, então o adaptador **consulta a API** para confirmar status
  `approved` (nunca confia no corpo do webhook); assinatura HMAC do header
  `x-signature` validada com `MP_WEBHOOK_SECRET`.

> ⚠️ Os dois adaptadores reais foram escritos contra a documentação pública e
> ainda **não foram validados contra o sandbox** (a sandbox desta sessão não
> tem rede externa). Antes de produção: rodar o roteiro de validação no
> sandbox do provedor.

## Deploy

```bash
cp .env.example .env   # preencha os tokens
# edite config.yaml (seller_numbers, provedores)
docker compose up -d --build
```

O banco (`pixzap.db`) fica no volume `pixzap-data`. O serviço expõe a porta
8000; coloque um proxy com HTTPS na frente (Meta e PSPs exigem webhook HTTPS).

## Endpoints

| Método/rota | Função |
|---|---|
| `GET /health` | status + versão |
| `GET /webhook/whatsapp` | handshake de verificação da Meta |
| `POST /webhook/whatsapp` | mensagens recebidas → comandos do bot |
| `POST /webhook/psp` | eventos de pagamento → conciliação |
| `GET /painel?token=...` | painel do vendedor (link mágico) |
| `GET /admin?token=...` | registros do administrador |

## Testes

```bash
python -m py_compile src/pixzap/**/*.py   # sanidade de sintaxe
python -m pytest tests                     # suíte completa (fakes, sem rede)
```

Cobertura dos testes: parsing de valores pt-BR, conciliação (confirmação,
idempotência, valor divergente, Pix órfão, cobrança cancelada), comandos do
bot (incluindo allowlist) e fluxo end-to-end pelo servidor (incluindo
rejeição de webhook não autenticado).

## Landing page e materiais de venda

- `site/index.html` — landing autocontida (fonte embutida, sem CDN), com
  demo animada do chat, seletor pt/EN/ES, preços e FAQ. Hospedar em
  qualquer estático (Cloudflare Pages, GitHub Pages); trocar o número do
  `wa.me` no CTA final antes de publicar.
- `docs/plano-de-negocios.md` — ICP, pricing, plano 30/60/90 dias para os
  primeiros clientes, fluxos de suporte/manutenção e rota de escala
  multi-tenant.

## Roadmap curto

- [ ] Validar adaptadores Asaas e Mercado Pago no sandbox real.
- [ ] Onboarding self-service pelo próprio chat (hoje: white glove).
- [ ] Multi-tenant (tabela sellers, credenciais de PSP por loja).
- [ ] Expiração automática de cobranças antigas (lembrete ao cliente).
- [ ] Alertas de erro do sistema no WhatsApp do admin.
- [ ] Exportação CSV pelo painel.

## Legado

Este repositório abrigava o **Phebos**, um bot de trading autônomo. O código
foi removido em jul/2026 (o dono tem backup e o histórico segue no git —
`git log` antes do commit "nasce o PixZap").
