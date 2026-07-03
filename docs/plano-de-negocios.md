# PixZap — Plano de negócios e go-to-market

**Data:** 02/07/2026 · **Objetivo:** primeiros clientes pagantes em 30 dias,
100 assinantes em 6 meses, sem investimento em mídia paga no início.

---

## 1. O negócio em uma frase

Assinatura mensal (R$ 49) que elimina a conferência manual de Pix e o golpe
do comprovante falso para quem vende pelo WhatsApp — o bot cobra no chat e
só confirma quando o dinheiro cai de verdade.

## 2. Cliente-alvo (ICP)

**Primário — "a revendedora":** vende roupas, semijoias, cosméticos,
importados ou comida por encomenda pelo WhatsApp/Instagram. 10-60 vendas/mês
por Pix, confere extrato no celular, já recebeu (ou teme) comprovante falso.
Decide sozinha, paga por Pix, mora no WhatsApp.

**Secundário:** delivery/lanchonete de bairro sem maquininha online;
prestadores de serviço (manicure, personal, aulas) que cobram sinal.

**Onde encontrá-los:** grupos de revenda no WhatsApp/Facebook, comunidades
de fornecedores (Brás/25 de Março, Goiânia moda), Instagram de fornecedores,
feiras locais.

## 3. Proposta de valor e pricing

| Plano | Preço | O que inclui | Papel no funil |
|---|---|---|---|
| Começando | R$ 0 | 20 confirmações/mês, 1 número | porta de entrada, boca a boca |
| Profissional | R$ 49/mês (lançamento) | ilimitado, 3 números, painel, suporte prioritário, exportação | receita |

Âncoras de valor na venda: **1 golpe evitado ≈ 1 ano de assinatura**;
**30 min/dia de extrato ≈ 15 h/mês** devolvidas. Meta de churn < 5%/mês
(o produto avisa dinheiro entrando — desligar dói).

Unit economics alvo: custo variável ≈ R$ 2-4/cliente/mês (Cloud API + infra
compartilhada) → margem bruta > 90%. CAC alvo ≈ R$ 0-30 (canais orgânicos).

## 4. Primeiros clientes — plano de 30/60/90 dias

### Dias 1-15 — validação paga ("lição MathPlanner": cobrar antes de escalar)
1. Escolher 3 nichos-piloto (ex.: revenda de roupas, semijoias, marmitas).
2. Entrar em 10 grupos/comunidades desses nichos (sem spam: participar).
3. Abordar 30 vendedores 1-a-1 com a pergunta-dor: *"Você confere Pix no
   extrato antes de enviar? Já levou comprovante falso?"*
4. Oferta fundadora para os 10 primeiros: **R$ 25/mês vitalício** + setup
   feito por nós na mão (white glove). Meta: **5 pagantes até o dia 15.**
5. Registrar cada objeção — vira copy da landing e FAQ.

### Dias 16-30 — provas sociais e rotina de venda
- Colher 3 depoimentos com print da confirmação real ("caiu e o bot avisou").
- Publicar a landing (`site/index.html`) com link wa.me e Pixel/UTM.
- Rotina diária: 10 abordagens novas + follow-up; 1 conteúdo curto
  (Reels/TikTok: "como identificar comprovante falso" → CTA PixZap).
- Meta: **15 pagantes, NPS informal > 8.**

### Dias 31-60 — canais que escalam sem mídia paga
- **Indicação com incentivo:** 1 mês grátis para quem traz 1 vendedor
  (mecânica dentro do próprio bot: comando "indicar").
- **Parcerias B2B2C:** fornecedores/atacadistas e "gurus de revenda"
  (cursos) divulgam para suas bases com cupom; comissão 30% recorrente.
- **SEO/conteúdo:** 10 artigos-alvo ("golpe do comprovante falso pix",
  "como conferir pix automaticamente", "bot de cobrança whatsapp") — busca
  com intenção altíssima e concorrência baixa; a pesquisa de LPs mostrou
  que orgânico composto é o canal nº 1 de indie SaaS.
- Meta: **40 pagantes.**

### Dias 61-90 — repetível e mensurável
- Padronizar onboarding self-service (hoje white glove) — ver §6.
- Dashboard de métricas de negócio (MRR, churn, ativação, confirmações/dia).
- Testar 1 canal pago pequeno (R$ 500 em anúncio no Instagram segmentado
  por interesse "revenda") só depois do orgânico validar a mensagem.
- Meta: **70-100 pagantes ≈ R$ 3,5-5 mil MRR.**

**Regra de decisão:** se no dia 30 não houver 10 pagantes reais, parar e
rever nicho/oferta antes de investir em escala (54% dos SaaS indie faturam
zero — a diferença é matar rápido o que não valida).

## 5. Fluxos do produto (decisão de design)

### Cliente (vendedor) — tudo pelo WhatsApp, como você sugeriu ✅
1. **Contratação:** clica no CTA da landing → abre conversa no nosso
   WhatsApp → o bot faz onboarding guiado (nome do negócio, PSP, idioma) →
   primeira cobrança de teste em ~5 min. Cobrança da assinatura: um Pix
   gerado pelo próprio PixZap (dogfooding) todo mês, com lembrete no chat.
2. **Uso diário:** `cobrar`, `pendentes`, `hoje` — zero app novo.
3. **Acompanhamento:** comando **`painel`** → **link mágico** (assinado,
   expira em 24 h, sem senha) abre o painel web com: recebido hoje/7 dias,
   pendências, histórico e alertas de divergência. *Já implementado.*
4. **Suporte:** o mesmo número; comando `suporte` abre chamado e um humano
   assume a conversa (handoff manual no início).

### Admin (nós)
- **Painel `/admin?token=...`** *(já implementado)*: todas as cobranças e
  webhooks com veredito da conciliação, alertas de divergência, volume.
- **Operação diária (15 min):** olhar alertas de conciliação, chamados de
  suporte e falhas de webhook; erros 5xx notificados no nosso próprio
  WhatsApp (roadmap curto).
- **Manutenção:** deploy Docker com volume persistente; backup diário do
  SQLite (cron + cópia para storage externo); logs estruturados; runbook no
  GUIA.md. Janela de atualização fora do horário comercial; healthcheck
  `/health` monitorado por UptimeRobot (grátis).
- **Suporte — SLAs simples:** plano pago < 2 h úteis; grátis < 24 h.
  Toda dúvida repetida vira item do FAQ/onboarding (reduz volume).

### Escala técnica (quando passar de ~50 lojas)
Hoje: 1 instância = 1 loja (simples e barato de operar).
Próximo passo: **multi-tenant** — tabela `sellers` (idioma, PSP, números),
`seller_id` em cobranças/pagamentos, roteamento por número de destino e
credenciais de PSP por loja (criptografadas). O código já isola PSP e
WhatsApp por trás de interfaces, então a migração é local (storage +
config), sem reescrever o produto.

## 6. Multi-idiomas e expansão geográfica

O produto já responde em **pt/en/es** (config `language`). A mesma dor
existe fora do Brasil sem Pix: transferência bancária na Nigéria/Quênia
(fake alert scam), SPEI no México, transferencias na Argentina/Colômbia.
A arquitetura de PSP plugável permite adaptar (ex.: Paystack/Flutterwave)
sem tocar no núcleo. Gatilho para internacionalizar: MRR estável no Brasil
(≥ R$ 10k) ou parceiro local forte.

## 7. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Meta banir/limitar número | Só API oficial; templates aprovados; número dedicado por região |
| PSP mudar API/webhook | Adaptadores isolados + testes de contrato; 2 PSPs suportados desde o dia 1 |
| Cópia por concorrente | Velocidade + nicho + marca ("screenshot não é comprovante"); dado proprietário de fraude |
| Inadimplência da assinatura | Cobrança via o próprio produto + downgrade automático para o plano grátis |
| Golpista usar o produto | KYC leve no onboarding (CPF/CNPJ do recebedor); monitorar volume atípico |

## 8. Metas e métricas (revisão semanal)

- **Norte:** MRR e nº de confirmações/semana (uso real).
- Ativação: % de novos que fazem 1ª cobrança em 24 h (alvo > 60%).
- Conversão landing → conversa (alvo 8-12%, benchmark de LPs de alta
  conversão) e conversa → pagante (alvo > 25% no white glove).
- Churn mensal < 5%; NPS > 50.

---

*Análise de mercado que embasa este plano:*
[analise-mercado-dores-globais.md](analise-mercado-dores-globais.md) ·
*Benchmarks de landing page:* [Unbounce](https://unbounce.com/conversion-rate-optimization/the-state-of-saas-landing-pages/),
[KlientBoost/Nudgify sobre prova social](https://www.nudgify.com/social-proof-landing-pages/),
[dados 2026 de conversão](https://firstpagesage.com/seo-blog/b2b-landing-page-conversion-rates/).
