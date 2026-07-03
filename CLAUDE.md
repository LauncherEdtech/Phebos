# Instruções para o Claude neste repositório

- Este repositório é o **PixZap** (bot de conciliação de Pix no WhatsApp).
  O antigo bot de trading (Phebos) é legado removido — não recriar.
- **Sempre atualize o `GUIA.md` a cada alteração no sistema** (novos recursos,
  comandos, configurações, dependências, deploy). Atualize também a linha
  "Última atualização" no topo dele.
- Documentação, mensagens de log e textos voltados ao usuário são em
  **português (pt-BR)**. Código (nomes de variáveis/funções) em inglês.
- Regras de segurança que nunca devem ser enfraquecidas sem pedido explícito:
  - pagamento só é confirmado por **webhook autenticado do PSP**
    (`verify_webhook` → 401 se falhar); nunca por mensagem/screenshot;
  - conciliação **exata ao centavo** e idempotente (`matching.py`);
  - **allowlist** de vendedores (`seller_numbers`) para comandos do bot;
  - transferências pelo chat: **desativadas por padrão**, com código de
    confirmação obrigatório e **limite diário** (`transfer_daily_limit`);
  - o assistente de IA (`assistant.py`) **nunca confirma pagamento nem
    executa ações**, e só vê dados financeiros com consentimento do
    vendedor (`assistente sim`/`assistente não`);
  - dinheiro sempre em **centavos (int)**; segredos só em variáveis de
    ambiente.
- Toda mensagem ao usuário sai do catálogo `i18n.py` (pt/en/es/id) — nada
  de string solta; novas chaves entram em TODOS os idiomas (há teste).
- WhatsApp: usar somente a **Cloud API oficial** (Meta); não introduzir
  bibliotecas não oficiais (Baileys etc.) sem o usuário pedir.
- Teste com `python -m py_compile src/pixzap/**/*.py` e `python -m pytest
  tests` — tudo roda com PSP/WhatsApp **fakes** (rede externa é bloqueada
  no sandbox).
