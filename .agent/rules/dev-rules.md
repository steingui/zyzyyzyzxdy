---
trigger: always_on
---

# Regras de Segurança e Execução
- **S01:** Credenciais de API (OpenAI/Anthropic) devem ser carregadas via ENV VAR.
- **S02:** O script de banco deve usar `COMMIT` apenas após a validação de todas as partidas da rodada.
- **S03:** Idempotência obrigatória: não inserir estatísticas para partidas que já possuem dados.