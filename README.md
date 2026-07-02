# PixZap — confirmação automática de Pix para quem vende pelo WhatsApp

> 📖 **Manual completo de instalação, uso e deploy: [GUIA.md](GUIA.md)**
> 📊 A análise de mercado que originou o produto: [docs/analise-mercado-dores-globais.md](docs/analise-mercado-dores-globais.md)

**O problema:** quem vende pelo WhatsApp confere pagamento na mão — o cliente
manda *screenshot* do comprovante e o vendedor precisa abrir o app do banco,
achar a transferência e casar com o pedido. Além de lento, é a porta de
entrada do **golpe do comprovante falso**.

**A solução:** o PixZap gera a cobrança Pix dentro do chat e só dá o pedido
como pago quando o dinheiro **realmente cai** (webhook autenticado do
provedor de pagamento). Screenshot deixa de valer como comprovante.

## Como funciona

```
Vendedor (WhatsApp): cobrar 150,00 João pedido 12
PixZap:              ✅ Cobrança #12 criada. Encaminhe o copia-e-cola: 000201...
   ... cliente paga o Pix ...
PSP  → webhook autenticado → PixZap concilia (txid + valor exato, em centavos)
PixZap (WhatsApp):   ✅ Pix de R$ 150,00 de Maria confirmado! Pode liberar. 🎉
```

Comandos do vendedor: `cobrar <valor> [descrição]` · `pendentes` · `hoje` ·
`cancelar <id>` · `ajuda`.

## Arquitetura

```
src/pixzap/
├── main.py         # ponto de entrada: monta dependências e sobe o servidor
├── server.py       # FastAPI: webhooks do WhatsApp e do PSP
├── bot.py          # comandos do vendedor no chat (pt-BR)
├── matching.py     # motor de conciliação determinístico (regra de ouro)
├── storage.py      # SQLite: cobranças e pagamentos
├── models.py       # domínio (dinheiro sempre em centavos, int)
├── config.py       # config.yaml + .env
├── psp/            # provedores de pagamento: fake | asaas | mercadopago
└── whatsapp/       # mensageria: fake | cloud (API oficial da Meta)
```

## Regras de segurança (nunca enfraquecer)

1. **Pagamento só se confirma por webhook autenticado do PSP** — nunca por
   mensagem, screenshot ou palpite. Webhook sem token/assinatura válida é
   descartado com HTTP 401.
2. **Conciliação exata ao centavo**: valor divergente NÃO quita a cobrança;
   o vendedor é alertado.
3. **Idempotência**: webhook repetido não gera confirmação nova.
4. **Allowlist de vendedores**: só números configurados dão comandos ao bot.

## Setup rápido (desenvolvimento)

```bash
pip install -e . && pip install pytest httpx
cp .env.example .env
python -m pytest tests          # tudo com fakes, sem rede externa
python -m pixzap.main           # sobe em http://localhost:8000 (PSP/WhatsApp fakes)
```

## Produção

1. Preencha `config.yaml` (números autorizados, provedores) e `.env` (tokens).
2. `docker compose up -d --build`
3. Configure os webhooks:
   - **Meta (WhatsApp)**: URL `https://seu-dominio/webhook/whatsapp` + o
     `WHATSAPP_VERIFY_TOKEN` que você inventou.
   - **PSP (Asaas/Mercado Pago)**: URL `https://seu-dominio/webhook/psp` + o
     token/assinatura no painel do provedor.

> Os adaptadores Asaas e Mercado Pago estão em **beta**: valide no sandbox do
> provedor antes de usar com dinheiro real.
