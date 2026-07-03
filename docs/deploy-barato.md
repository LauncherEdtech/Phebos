# Deploy na stack mais barata possível (Oracle Always Free + API oficial da Meta)

**Custo total:** R$ 0/mês de servidor + ~R$ 40/ano de domínio + centavos de
template da Meta. Atualizado em 03/07/2026.

## Por quanto tempo a Oracle é grátis?

O **Always Free não expira**: vale pela vida da conta, não é trial
([FAQ oficial](https://www.oracle.com/cloud/free/faq/),
[docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)).
Duas pegadinhas para conhecer:

1. **Limites novos desde jun/2026:** contas free têm agora 2 OCPUs ARM +
   12 GB de RAM no total (era 4/24). Sobra de folga: o PixZap roda
   confortável com 1 OCPU + 2 GB.
2. **Recuperação por ociosidade:** VM free com CPU abaixo de 20% (p95) por
   7 dias pode ser recuperada pela Oracle. Duas defesas: converter a conta
   para **Pay As You Go** (os recursos Always Free continuam gratuitos,
   sem cobrança dentro dos limites, e deixam de sofrer reclaim) e/ou o
   UptimeRobot batendo no `/health` a cada 5 min já gera atividade.

Existe também um trial separado de US$ 300 por 30 dias, que não nos
interessa — o que usamos é o Always Free permanente.

## Passo a passo

### 1. Servidor (Oracle Always Free)

1. Crie a conta em oracle.com/cloud/free (pede cartão para verificação,
   não cobra). Escolha home region **Brazil East (São Paulo)**.
2. Compute → Create Instance → shape **VM.Standard.A1.Flex** (1 OCPU,
   2-6 GB), imagem **Ubuntu 22.04/24.04**. Guarde a chave SSH.
3. Networking → Virtual Cloud Network → Security List: libere ingress TCP
   **80** e **443** (0.0.0.0/0).
4. (Recomendado) Billing → Upgrade to Pay As You Go, pelo motivo acima.

### 2. Domínio e DNS

1. Registre `seudominio.com.br` no Registro.br (~R$ 40/ano).
2. Crie um registro **A**: `api.seudominio.com.br` → IP público da VM.
3. Landing page: suba `site/index.html` no **Cloudflare Pages** (grátis)
   apontando `www`/raiz para lá. Troque o número do `wa.me` no CTA antes.

### 3. Bot na VM

```bash
ssh ubuntu@IP
git clone https://github.com/LauncherEdtech/Phebos.git pixzap && cd pixzap
bash setup.sh            # instala Docker, pergunta as chaves, sobe o serviço
```

Edite `config.yaml`: `seller_numbers`, `public_url: "https://api.seudominio.com.br"`,
`whatsapp.provider: cloud`, `psp.provider: asaas`.

### 4. HTTPS com Caddy (certificado automático e gratuito)

```bash
sudo apt install -y caddy
echo 'api.seudominio.com.br {
    reverse_proxy localhost:8000
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Teste: `https://api.seudominio.com.br/health` deve responder `{"status":"ok"}`.

### 5. API oficial da Meta (WhatsApp Business Cloud API)

Sem mensalidade; integração direta, sem BSP. Checklist:

1. **App:** developers.facebook.com → Create App → tipo Business →
   adicionar produto **WhatsApp**.
2. **Número:** na aba API Setup, adicione um número novo (chip pré-pago
   dedicado que nunca usou WhatsApp). Para testar antes, use o test number
   gratuito que a Meta fornece.
3. **Token permanente:** Business Settings → Users → **System Users** →
   criar admin → gerar token com escopos `whatsapp_business_messaging` e
   `whatsapp_business_management` → vai no `.env` como
   `WHATSAPP_ACCESS_TOKEN` (o token da tela de API Setup expira em 24 h,
   não use em produção).
4. **Webhook:** Configuration → Webhooks → URL
   `https://api.seudominio.com.br/webhook/whatsapp`, verify token = o que
   você inventou no `.env` (`WHATSAPP_VERIFY_TOKEN`); assinar o campo
   **messages**.
5. **`phone_number_id`:** copie da tela API Setup para o `config.yaml`.
6. **Template de janela fechada (importante):** WhatsApp Manager →
   Message Templates → criar template **utility** com nome
   `pixzap_notificacao`, idioma pt_BR e corpo exatamente `{{1}}`.
   É ele que o sistema usa automaticamente quando a confirmação de
   pagamento chega com a janela de 24 h fechada (US$ 0,008/msg; dentro da
   janela tudo é grátis). Aprovação costuma sair em minutos/horas.
7. **Modo produção:** App Review → mudar o app de Development para Live
   (exige Privacy Policy URL — a landing serve de base para criar uma
   página simples de privacidade).

### 6. PSP (Asaas)

1. Conta em asaas.com (sandbox primeiro: sandbox.asaas.com).
2. Integrações → API Key → `.env` (`ASAAS_API_KEY`).
3. Webhooks → URL `https://api.seudominio.com.br/webhook/psp`, token de
   autenticação = `ASAAS_WEBHOOK_TOKEN` do `.env`, evento
   **PAYMENT_RECEIVED**.
4. Cadastre a chave Pix no Asaas e preencha `psp.asaas_pix_key`.

### 7. Pós-deploy

- UptimeRobot (grátis) monitorando `https://api.seudominio.com.br/health`.
- Backup diário do banco: `crontab -e` →
  `0 3 * * * docker cp $(docker ps -qf name=pixzap):/app/data/pixzap.db /home/ubuntu/backup/pixzap-$(date +\%u).db`
- Fluxo de teste ponta a ponta: mandar `ajuda` do número autorizado →
  `cobrar 1,00 teste` → pagar o Pix de R$ 1 → conferir a confirmação.
