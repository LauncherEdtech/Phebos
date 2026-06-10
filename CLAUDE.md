# Instruções para o Claude neste repositório

- **Sempre atualize o `GUIA.md` a cada alteração no sistema** (novos recursos,
  comandos, configurações, dependências, deploy). Atualize também a linha
  "Última atualização" no topo dele.
- Documentação, mensagens de log e textos voltados ao usuário são em
  **português (pt-BR)**. Código (nomes de variáveis/funções) em inglês.
- O analista usa a **API do Gemini** (`google-genai`); não reintroduzir outras
  dependências de LLM sem o usuário pedir.
- Regras de segurança que nunca devem ser enfraquecidas sem pedido explícito:
  trava do modo live (`PHEBOS_CONFIRM_LIVE`), motor de risco determinístico
  (`risk.py`) e kill switch (arquivo `KILL`).
- Teste com `python -m py_compile src/phebos/**/*.py` e rode os fluxos com
  brokers/analista fakes (rede externa é bloqueada no sandbox).
