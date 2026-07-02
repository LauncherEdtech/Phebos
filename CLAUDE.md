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
  - dinheiro sempre em **centavos (int)**; segredos só em variáveis de
    ambiente.
- WhatsApp: usar somente a **Cloud API oficial** (Meta); não introduzir
  bibliotecas não oficiais (Baileys etc.) sem o usuário pedir.
- Teste com `python -m py_compile src/pixzap/**/*.py` e `python -m pytest
  tests` — tudo roda com PSP/WhatsApp **fakes** (rede externa é bloqueada
  no sandbox).
