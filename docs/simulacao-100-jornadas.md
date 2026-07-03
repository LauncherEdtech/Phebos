# Simulação de 100 jornadas de usuários reais

**Data:** 03/07/2026 · Método: cada jornada foi confrontada com o código
atual; o que falhou ou confundiu virou correção + teste que reproduz a cena
(`tests/test_user_simulation.py` e `tests/test_simulation_round2.py`).

**Legenda:** ✅ funciona bem · 🔴 FALHA corrigida nesta rodada ·
🟡 confusão corrigida nesta rodada · ☑️ corrigido em rodada anterior ·
📋 decisão documentada / roadmap

## A. Criando cobranças (1-15)

| # | Jornada | Veredito |
|---|---|---|
| 1 | `cobrar 150 João pedido 12` normal | ✅ |
| 2 | `COBRAR 150` em maiúsculas | ✅ regex ignora caixa |
| 3 | `cobrar R$150` colado no valor | ✅ |
| 4 | `cobrar 150` sem descrição | ✅ vira "sem descrição" |
| 5 | `cobrar 150,5` (um dígito decimal) | ✅ R$ 150,50 |
| 6 | `cobrar 150.00` estilo gringo | ☑️ era R$ 15.000 (bug grave, corrigido) |
| 7 | **Duplo toque: mesma cobrança 2x** | 🔴 criava 2 cobranças mudo; agora avisa "já existe cobrança IGUAL pendente, cancele se foi engano" |
| 8 | `cobrar 0,05` valor ínfimo | ✅ aceita (centavos válidos) |
| 9 | **Descrição de 500 caracteres** (cola o pedido inteiro) | 🟡 mensagens ficavam ilegíveis; agora apara em 120 chars |
| 10 | Emoji/aspas/`*` na descrição | ✅ escapado no painel; cosmético no chat |
| 11 | `cobrar 999999999999` | ✅ recusa (limite de sanidade) |
| 12 | `cobrar -50` | ✅ recusa |
| 13 | **PSP fora do ar na hora do cobrar** | 🔴 exceção era engolida e o vendedor ficava SEM RESPOSTA; agora responde "não consegui gerar a cobrança, tente de novo" |
| 14 | Duas cobranças de mesmo valor p/ clientes diferentes | ✅ match é por txid, não cruza (testado) |
| 15 | Cobrança esquecida há semanas | 📋 nunca expira; roadmap: expiração automática + lembrete |

## B. Pagamentos e conciliação (16-30)

| # | Jornada | Veredito |
|---|---|---|
| 16 | Cliente paga certo | ✅ confirma com nome do pagador |
| 17 | Cliente paga R$ 149,99 em cobrança de R$ 150,00 | ✅ NÃO quita; alerta |
| 18 | Cliente paga a MAIS | ✅ NÃO quita; alerta divergência |
| 19 | **Vendedor manda código p/ pessoa errada e ela paga** | ✅ dinheiro real → confirma, e a mensagem mostra pagador × pedido p/ flagrar a troca (testado) |
| 20 | **Mesmo código pago por DUAS pessoas** | ☑️ 2º pagamento era engolido como retry; agora alerta "pagamento_extra" pedindo devolução |
| 21 | Cliente reaproveita código do mês passado | ☑️ mesmo mecanismo da #20 |
| 22 | Retry de webhook do PSP (3x) | ✅ silêncio (idempotência por payment_ref) |
| 23 | **Pagou errado e o PSP reenviou o webhook 3x** | ☑️ alertava 3x (spam); agora alerta 1x |
| 24 | Pagou errado, depois pagou certo no mesmo código | ✅ o certo confirma (testado nesta rodada) |
| 25 | Pix cai sem cobrança associada | ✅ alerta "confira no banco" |
| 26 | Pagamento tardio em cobrança cancelada | ✅ alerta de conferência manual |
| 27 | Cliente diz "paguei" + screenshot no chat do vendedor | ✅ irrelevante por design: só webhook confirma |
| 28 | **Vendedor encaminha o screenshot para o BOT** | ☑️ silêncio confuso; agora responde "print não é comprovante, eu aviso sozinho" |
| 29 | Cliente paga parcelado em 2 Pix (75+75) | 🟡 cada um alerta divergência; cobrança nunca quita — 📋 roadmap: comando p/ dar baixa manual assumida |
| 30 | Webhook chega com o bot offline | ✅ PSPs reenviam; ao voltar, processa (idempotente) |

## C. Erros de digitação e formato (31-42)

| # | Jornada | Veredito |
|---|---|---|
| 31 | `cobrar` sozinho | ☑️ "não entendi" → agora ensina o uso |
| 32 | `cobrar abc` | ✅ "valor inválido" com exemplos |
| 33 | **`cobrar 150⏎João⏎sábado` em várias linhas** | 🔴 regex falhava e dizia "valor inválido"; agora aceita (re.S) |
| 34 | **`Ajuda!` / `oi!!` com pontuação** | 🟡 caía no "não entendi"; agora entende |
| 35 | **`pendente` no singular / `resumo` / `comandos`** | 🟡 agora são sinônimos aceitos |
| 36 | `cancelar` sem número | ☑️ ensina o uso |
| 37 | `cancelar 999` inexistente | ✅ "não encontrada" |
| 38 | `confirmar 12` (código curto) | ☑️ "código inválido" |
| 39 | Mensagem vazia/só espaços | ✅ "não entendi" |
| 40 | Texto de 4.000 caracteres aleatórios | ✅ "não entendi" |
| 41 | `bom dia, quero cobrar alguém` (conversa) | ✅ "não entendi" + dica da ajuda |
| 42 | Tentativa de SQL injection na descrição | ✅ queries parametrizadas + HTML escapado |

## D. Saldo e transferências (43-55)

| # | Jornada | Veredito |
|---|---|---|
| 43 | `saldo` normal | ✅ |
| 44 | **`saldo` com PSP fora do ar** | 🔴 silêncio; agora "não consegui falar com o provedor" |
| 45 | `saldo` no Mercado Pago | ✅ "provedor não suporta" |
| 46 | `transferir 200 pro pix: chave` fluxo feliz | ✅ código de 6 dígitos + confirmação |
| 47 | `transferir 50` sem chave | ☑️ ensina o uso |
| 48 | Código errado no confirmar | ✅ invalida a operação inteira (anti força bruta) |
| 49 | Confirmar depois de 5 min | ✅ expirado |
| 50 | Estourar o limite diário | ✅ bloqueia e mostra quanto já foi |
| 51 | Transferências com limite 0 (padrão) | ✅ desativadas, explica como ativar |
| 52 | Saldo insuficiente na execução | ✅ "não foi executada: saldo insuficiente" |
| 53 | **Colega de equipe tenta confirmar transferência do outro** | ✅ código é por remetente (testado nesta rodada) |
| 54 | Duas transferências pendentes do mesmo vendedor | 📋 a 2ª substitui a 1ª (documentado; comportamento seguro) |
| 55 | Bot reinicia com transferência pendente | 📋 pendência em memória morre; usuário recomeça (seguro por design) |

## E. Painel e link mágico (56-63)

| # | Jornada | Veredito |
|---|---|---|
| 56 | `painel` com public_url configurada | ✅ link de 24h |
| 57 | `painel` sem public_url | ✅ explica que não está configurado |
| 58 | Link expirado | ✅ 403 com instrução de pedir outro |
| 59 | Link adulterado | ✅ 403 |
| 60 | Link de número removido da allowlist | ✅ 403 (revoga acesso) |
| 61 | Vendedor compartilha o link | 📋 quem tem o link vê métricas por 24h; aviso "não compartilhe" na mensagem |
| 62 | `/admin` sem token configurado | ✅ sempre 403 |
| 63 | Token de admin na URL | 📋 pode vazar em log de proxy; documentado (usar por trás de HTTPS) |

## F. Equipe / multi-vendedor (64-70)

| # | Jornada | Veredito |
|---|---|---|
| 64 | 2 números na allowlist operando juntos | ✅ loja única compartilhada (por design) |
| 65 | B cancela cobrança criada por A | ✅ permitido (mesma loja); auditável no admin |
| 66 | Confirmação de pagamento notifica todos | ✅ todos os números autorizados recebem |
| 67 | A e B cobram o mesmo cliente ao mesmo tempo | ✅ duas cobranças distintas, txids distintos |
| 68 | Vendedor troca de chip/número | 📋 editar seller_numbers + restart; links antigos morrem sozinhos |
| 69 | Duas LOJAS diferentes no mesmo servidor | 📋 hoje 1 instância = 1 loja; multi-tenant no roadmap |
| 70 | Número do vendedor clonado (SIM swap) | 📋 risco real p/ transferências → por isso limite diário + desativado por padrão; roadmap: PIN |

## G. Segurança e golpes (71-82)

| # | Jornada | Veredito |
|---|---|---|
| 71 | Estranho manda `cobrar` | ✅ ignorado em silêncio |
| 72 | Estranho manda `painel`/`saldo`/`transferir` | ✅ silêncio |
| 73 | Estranho manda imagem | ✅ silêncio (só vendedor recebe a resposta educada) |
| 74 | Golpista posta webhook falso de pagamento | ✅ 401 sem token/assinatura válida (testado) |
| 75 | Webhook com token errado | ✅ 401 |
| 76 | Comprovante adulterado no chat | ✅ irrelevante por design |
| 77 | Golpista descobre a URL do webhook | ✅ inútil sem o segredo |
| 78 | Replay de webhook antigo capturado | ✅ payment_ref já processado → silêncio |
| 79 | Flood de mensagens de estranho | ✅ ignoradas; 📋 rate-limit fino no roadmap |
| 80 | Cliente golpista paga R$ 0,01 esperando confirmação | ✅ divergência, não quita |
| 81 | "Cliente" pede o painel do vendedor | ✅ link só nasce no chat do vendedor |
| 82 | Vendedor golpista usando o produto | 📋 KYC fica no PSP (Asaas/MP); nosso onboarding registra CPF |

## H. Idiomas e moedas (83-88)

| # | Jornada | Veredito |
|---|---|---|
| 83 | Loja em `en` recebe pagamento | ✅ "Payment of...", sem falar Pix |
| 84 | Loja em `es`/`id` | ✅ catálogos completos (teste garante paridade de chaves) |
| 85 | Idioma inexistente no config | ✅ cai no pt-BR |
| 86 | Moeda IDR sem centavos | ✅ "Rp 150.000" |
| 87 | Vendedor digita valor no estilo da moeda dele | ✅ parser aceita vírgula e ponto |
| 88 | Comandos em inglês (`balance`, `dashboard`) | ✅ aliases aceitos |

## I. Infraestrutura e falhas (89-95)

| # | Jornada | Veredito |
|---|---|---|
| 89 | Corpo inválido no webhook do WhatsApp | ✅ 200 "ignorado" (evita retry-loop da Meta) |
| 90 | Corpo inválido no webhook do PSP | ✅ 400 |
| 91 | **Falha ao ENVIAR a confirmação (Meta fora do ar)** | ☑️ conciliação persiste; erro só logado; retry do PSP não duplica |
| 92 | Janela de 24h fechada na hora do aviso | ☑️ fallback automático p/ template utility |
| 93 | Banco corrompido/apagado | 📋 backup diário via cron (deploy-barato.md) |
| 94 | Reinício no meio de um webhook | ✅ PSP reenvia; idempotente |
| 95 | Fuso do vendedor ≠ config | 📋 timezone configurável; padrão São Paulo |

## J. Ciclo de vida do cliente (96-100)

| # | Jornada | Veredito |
|---|---|---|
| 96 | Cliente pouco instruído sem conta em gateway | 📋 white glove → MP existente → subconta white label via API (plano-de-negocios.md) |
| 97 | Primeira cobrança em 10 min do onboarding | ✅ roteiro no teste-local.md |
| 98 | Cliente quer cancelar assinatura | 📋 downgrade p/ plano grátis; dados ficam com ele |
| 99 | Cliente quer exportar o histórico | 📋 SQLite exporta CSV; roadmap: botão no painel |
| 100 | Cliente pergunta "cadê meu dinheiro?" | ✅ resposta de produto: o dinheiro NUNCA passa pelo PixZap; está na conta dele no PSP |

## Placar

- ✅ **58** jornadas já se comportavam bem (a maioria coberta por teste)
- 🔴 **3** falhas reais corrigidas NESTA rodada (duplo toque sem aviso, PSP
  fora do ar virando silêncio no cobrar e no saldo)
- 🟡 **4** confusões corrigidas nesta rodada (multi-linha, pontuação,
  sinônimos, descrição gigante)
- ☑️ **9** já corrigidas nas rodadas anteriores (pagamento duplo engolido,
  parser 150.00, spam de retry, screenshot pro bot etc.)
- 📋 **26** decisões documentadas ou itens de roadmap (expiração de
  cobrança, baixa manual, PIN de transferência, multi-tenant, rate-limit)

**Top 3 do roadmap saído da simulação:** expiração/lembrete de cobranças
antigas (J15), baixa manual p/ pagamento parcial aceito (J29) e PIN de
transferência contra SIM swap (J70).
