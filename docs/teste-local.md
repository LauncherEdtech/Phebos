# Testando o PixZap localmente (antes da VM), com a API oficial da Meta

É totalmente possível: o servidor roda na sua máquina e um túnel gratuito
dá a URL HTTPS pública que a Meta exige para webhooks. Atualizado em
03/07/2026.

## O que você vai precisar

- Python 3.10+ (ou Docker)
- Conta em developers.facebook.com (gratuita)
- `cloudflared` (túnel gratuito da Cloudflare, sem conta) — alternativa: ngrok
- Seu WhatsApp pessoal no celular (vai ser o "vendedor")

## Etapa 1 — Rodar o servidor local

```bash
git clone https://github.com/LauncherEdtech/Phebos.git pixzap && cd pixzap
pip install -e .
cp .env.example .env
```

Edite o `config.yaml`:

```yaml
seller_numbers: ["55SEUNUMERO"]   # seu WhatsApp pessoal, ex.: 5511999998888
whatsapp:
  provider: cloud
  phone_number_id: ""             # vem da etapa 3
psp:
  provider: fake                  # comece com o fake; Asaas sandbox depois
```

```bash
python -m pixzap.main             # sobe em http://localhost:8000
curl localhost:8000/health        # → {"status":"ok"}
```

## Etapa 2 — Túnel HTTPS gratuito

```bash
# instala o cloudflared (Linux; no Windows/Mac baixe do site da Cloudflare)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://localhost:8000
```

Ele imprime algo como `https://abc-def-ghi.trycloudflare.com` — essa é a
sua URL pública. **Atenção: a URL muda a cada execução do túnel**; quando
reiniciar, atualize o webhook na Meta (etapa 3).

## Etapa 3 — App na Meta com o número de teste (grátis)

1. developers.facebook.com → **Create App** → tipo *Business* → adicione o
   produto **WhatsApp**.
2. Na tela **API Setup** a Meta já te dá um **número de teste gratuito**.
   Copie o **Phone number ID** para o `config.yaml` e o **token temporário**
   (24 h, suficiente para testar) para o `.env` em `WHATSAPP_ACCESS_TOKEN`.
3. Ainda em API Setup → **To** → *Manage phone number list* → adicione o
   seu WhatsApp pessoal (o número de teste só conversa com até 5 números
   cadastrados — limitação do modo teste, some com número real).
4. Invente um segredo e coloque em `WHATSAPP_VERIFY_TOKEN` no `.env`.
   Reinicie o `python -m pixzap.main`.
5. **Configuration → Webhooks**: URL =
   `https://SUA-URL.trycloudflare.com/webhook/whatsapp`, verify token = o
   segredo do passo 4 → *Verify and save* (o handshake `GET` já está
   implementado). Depois assine o campo **messages**.

## Etapa 4 — Conversar de verdade

No seu WhatsApp pessoal, mande mensagem para o número de teste:

```
ajuda                       → menu completo
cobrar 1,00 teste pedido 1  → volta o "copia-e-cola" (fake)
pendentes                   → lista a cobrança
```

## Etapa 5 — Simular o dinheiro caindo (PSP fake)

Pegue o `txid` da cobrança (aparece no painel `/admin` ou no banco) e:

```bash
curl -X POST localhost:8000/webhook/psp \
  -H 'Content-Type: application/json' -H 'x-fake-token: teste' \
  -d '{"event":"PAYMENT_RECEIVED","txid":"FAKE00000001","amount_cents":100,"payer_name":"Maria","payment_ref":"PAY1"}'
```

→ a confirmação "✅ Pix de R$ 1,00 de Maria confirmado!" chega no seu
WhatsApp de verdade. Cenários para repetir os testes de simulação:

- **valor errado:** mande `amount_cents` diferente → alerta de divergência;
- **pagamento em dobro:** repita com `"payment_ref":"PAY2"` → alerta de
  segundo pagamento;
- **retry de webhook:** repita com o MESMO `payment_ref` → silêncio (nada
  duplicado);
- **Pix órfão:** use um `txid` inexistente → alerta de Pix sem cobrança.

## Etapa 6 — Trocar o fake pelo Asaas sandbox (opcional)

1. Conta em sandbox.asaas.com → API Key → `.env` (`ASAAS_API_KEY`), token
   de webhook em `ASAAS_WEBHOOK_TOKEN`.
2. `config.yaml`: `psp.provider: asaas`, `asaas_sandbox: true`,
   `asaas_pix_key` = chave criada no sandbox.
3. No painel do sandbox: Webhooks → URL
   `https://SUA-URL.trycloudflare.com/webhook/psp`, mesmo token, evento
   PAYMENT_RECEIVED.
4. O sandbox tem botão de simular pagamento — o fluxo fica 100% real,
   sem dinheiro de verdade.

## Limitações do modo teste (somem em produção)

| Limitação | Motivo |
|---|---|
| Token expira em 24 h | Token da tela API Setup; o permanente vem do System User (ver deploy-barato.md §5.3) |
| Só conversa com 5 números | Número de teste da Meta |
| Template customizado indisponível | Número de teste só tem o `hello_world`; o fallback de janela fechada (`pixzap_notificacao`) só dá para testar com número real |
| URL do túnel muda a cada restart | Quick tunnel; na VM usa domínio fixo |
