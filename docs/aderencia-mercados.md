# Aderência do PixZap por mercado — e o que isso muda no produto

**Data:** 03/07/2026 · Complementa a
[análise de dores globais](analise-mercado-dores-globais.md) e o
[plano de negócios](plano-de-negocios.md).

## Critérios de aderência

1. **Dor documentada** de comprovante/alerta falso atingindo vendedores.
2. **Trilho de pagamento instantâneo** com PSPs que expõem webhook.
3. **WhatsApp como canal de venda** dominante no varejo informal.
4. Facilidade de entrada (idioma, moeda, regulação, concorrência).

## Ranking

| # | Mercado | Trilho | Dor documentada | Idioma no produto | Moeda |
|---|---|---|---|---|---|
| 1 | **Brasil** | Pix | Golpe do comprovante falso; maior receita do WhatsApp Business do mundo | `pt` (padrão) | `BRL` |
| 2 | **Índia** | UPI | Epidemia de screenshot falso de GPay/PhonePe/Paytm; até ferramentas de detecção viraram negócio ([Razorpay](https://razorpay.com/learn/fake-payment-screenshot-scam/), [Cashfree](https://www.cashfree.com/blog/fake-payment-screenshot-scams/), [ScamDekho](https://scamdekho.in/fake-payment-screenshot-checker)) | `en` | `INR` |
| 3 | **Indonésia** | QRIS/transfer | "Bukti transfer palsu" com alerta do Bank Indonesia; golpes com IA gerando comprovantes ([Jalin](https://www.jalin.co.id/id-id/berita/blog/waspadai-bukti-transfer-palsu-lindungi-bisnismu-dari-modus-baru), [Tempo](https://www.tempo.co/ekonomi/penipuan-transfer-palsu-dengan-ai-bank-indonesia-minta-nasabah-teliti-cek-transaksi-1230535)) | `id` (novo) | `IDR` |
| 4 | **Nigéria/Quênia** | transferência/M-Pesa | "Fake bank alert" com táticas avançadas (double alert, value date, malware de overlay) ([CIRE](https://cire.com.ng/blogs/advanced-fake-bank-alert-tactics-nigeria)); WhatsApp é a plataforma de negócio das PMEs (confirmado 3-0 na análise anterior) | `en` | `NGN`/`KES` |
| 5 | **México/Colômbia/Argentina** | SPEI/transfer | Social commerce de US$ 15B via WhatsApp na LATAM; WhatsApp Pay em teste no México | `es` | `MXN`/`COP`/`ARS` |

Observações que pesaram no ranking:

- **Índia** tem a maior base de WhatsApp do mundo (rumo a 1 bilhão de
  usuários) e a fraude mais documentada, mas também a maior concorrência:
  os soundboxes de PhonePe/Paytm já anunciam pagamento em voz alta no
  balcão. O espaço do PixZap lá é o vendedor social (sem loja física).
- **Indonésia** é o 3º maior mercado de WhatsApp e a dor é idêntica à
  brasileira, com pouquíssima solução local voltada ao vendedor informal.
- **Nigéria** valida a dor com mais força (até malware de overlay), mas a
  infraestrutura de PSP com webhook é menos padronizada; entrar via
  parceiro local (Paystack/Flutterwave) num segundo momento.

## O que já foi ajustado no produto por causa desta análise

1. **Idioma `id` (indonésio)** adicionado ao bot, às notificações e ao
   painel; landing page também ganhou o idioma.
2. **Traduções recalibradas por trilho de pagamento**: `en` fala
   *payment/transfer* (UPI e transferência bancária não são "Pix"), `es`
   fala *pago/transferencia* (mundo SPEI), `id` fala *transfer* — só o
   `pt` fala "Pix".
3. **Moeda configurável** (`currency` no config.yaml): BRL, INR, IDR, NGN,
   KES, MXN, COP, ARS, USD, com formatação certa em cada uma (Rp sem
   centavos, ₦ com ponto decimal etc.) e parser que aceita `150,50` e
   `150.50`.

## Sequência recomendada

Brasil primeiro (idioma, PSPs prontos, conhecimento local), Indonésia como
segunda aposta (dor idêntica + concorrência baixa + idioma já no produto),
Índia via nicho social-seller, África via parceiro. A decisão de expandir
continua atrelada ao gatilho do plano de negócios: MRR estável no Brasil.
