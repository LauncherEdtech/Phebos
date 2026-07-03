# Criar conta de gateway pelo chat do WhatsApp — é possível?

**Data:** 03/07/2026 · **Resposta curta: sim, por duas rotas com trade-offs
bem diferentes.**

## Rota A — Subconta white label do Asaas (conta completa, 100% no chat)

O Asaas expõe criação de subcontas por API
([POST /v3/accounts](https://docs.asaas.com/reference/criar-subconta),
[guia white label](https://docs.asaas.com/docs/cria%C3%A7%C3%A3o-de-subcontas-whitelabel)):

1. **Dados básicos via chat:** nome, CPF/CNPJ, e-mail, celular, data de
   nascimento, endereço e **faturamento mensal (`incomeValue`, obrigatório)**
   — tudo coisa que o cliente digita numa conversa guiada.
2. **KYC sem sair do WhatsApp:** para PF/MEI o Asaas exige documento de
   identidade + selfie, e aceita o envio **via API** (ou por link
   `onboardingUrl`) ([fluxo de aprovação](https://docs.asaas.com/docs/detalhamento-do-fluxo-de-aprova%C3%A7%C3%A3o-de-subcontas),
   [envio de documentos](https://docs.asaas.com/docs/onboarding-e-envio-de-documentos-via-link)).
   Como o WhatsApp entrega mídia pela Cloud API, o fluxo fica: cliente tira
   a selfie no próprio chat → baixamos a mídia → subimos no Asaas por API.
   O cliente nunca vê o painel do Asaas.
3. **Aprovação em até 48 h**, com webhook de status. Detalhe de
   implementação: aguardar ~15 s após criar a conta antes de consultar
   pendências de documentos.
4. Cada subconta nasce com **apiKey e walletId próprios**: o dinheiro cai
   na conta DO CLIENTE (KYC e regulação com o Asaas), e dá para configurar
   **split automático da nossa mensalidade/comissão** na própria cobrança.

**Pré-requisitos:** o modo white label precisa ser **alinhado com o gerente
de conta do Asaas** (contato comercial, não é só técnico) e, do nosso lado,
o **multi-tenant** (credencial por loja, criptografada).

**Encaixe com a promessa da marca:** perfeito — "seu dinheiro não passa
pela gente" continua verdadeiro.

## Rota B — Subconta leve do OpenPix/Woovi (nem precisa criar conta)

O modelo do [OpenPix/Woovi](https://developers.openpix.com.br/en/docs/subaccount/how-to-get-balance-and-details-of-subaccount-using-api)
é mais radical: a "subconta" é só **um nome + a chave Pix que o cliente já
tem no banco dele** ([casos de uso de split](https://developers.openpix.com.br/en/docs/subaccount/split-sub-account-usecases)).

- Onboarding de ~30 segundos no chat: "qual sua chave Pix?" e pronto.
- As cobranças saem da NOSSA conta master; o valor de cada venda acumula
  na subconta do vendedor e o **saque para a chave Pix dele** sai por API
  (manual ou automático), com split da nossa comissão embutido.

**Trade-off importante:** o dinheiro transita pela nossa conta master no
OpenPix (sub-razão contábil), então a promessa vira "seu dinheiro fica na
OpenPix em nome da sua subconta, sacável a qualquer momento" — mais
fricção de confiança e nos aproxima do papel de marketplace. Em
compensação, elimina TODO o atrito de cadastro e o prazo de 48 h.

## E os outros?

| Gateway | Conta via API? | Observação |
|---|---|---|
| **Asaas** | ✅ white label completa | exige alinhamento comercial |
| **OpenPix/Woovi** | ✅ (modelo leve, só chave Pix) | dinheiro na conta master |
| Pagar.me / Iugu | ✅ recebedores/subcontas p/ marketplace | mesmo modelo do Asaas, contrato comercial |
| **Mercado Pago** | ❌ criação por API não existe | só OAuth de conta EXISTENTE (passo no navegador) |

## Recomendação

1. **Fase white glove (agora):** nada muda — conta Asaas criada junto na
   chamada.
2. **Fase self-service:** implementar a **Rota A** junto com o multi-tenant
   (é a que preserva a promessa da marca). Abrir a conversa comercial com
   o Asaas **antes** de codar, porque o white label depende de aprovação
   deles.
3. Manter a **Rota B** como plano alternativo se o atrito do KYC (docs +
   48 h) derrubar a conversão do onboarding — dá para testar com uma
   coorte pequena e medir.

## Esboço do fluxo da Rota A no chat (quando implementarmos)

```
Cliente: quero começar
Bot: Bora! Seu nome completo?           → nome
Bot: Seu CPF? (só números)              → valida dígito
Bot: E-mail? / Nascimento? / Cidade?    → coleta guiada
Bot: Quanto você vende por mês, mais ou menos? → incomeValue
Bot: Agora me manda uma foto do seu RG ou CNH 📷 → mídia → API Asaas
Bot: E uma selfie segurando o documento 🤳       → mídia → API Asaas
Bot: Pronto! Conta em análise (até 48h). Eu te aviso aqui. ✅
[webhook de aprovação] Bot: Conta aprovada! Manda *cobrar 1,00 teste* 🎉
```
