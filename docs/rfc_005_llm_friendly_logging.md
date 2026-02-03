# RFC 005: Padronização de logs amigáveis para LLM (Format TOON)

**Status:** ✅ Implementado

## 1. Contexto
Os logs da aplicação precisam ser otimizados para consumo por LLMs (Agentes). O formato texto livre é difícil de parsear, e JSON, embora estruturado, é verboso e consome muitos tokens devido à repetição de chaves e sintaxe (`{ "key": "value" }`).

## 2. Objetivo
Migrar o sistema de logging para o formato **TOON (Token-Oriented Object Notation)**. 
O TOON é projetado especificamente para LLMs, combinando a legibilidade do YAML (para hierarquias) com a concisão do CSV (para listas), reduzindo drasticamente o consumo de tokens enquanto mantém a estrutura.

## 3. Princípios

### 3.1. Formato TOON
Em vez de JSON:
```json
{
  "timestamp": "2026...",
  "level": "INFO",
  "data": { "key": "val" }
}
```

Utilizar TOON:
```yaml
timestamp: 2026...
level: INFO
data:
  key: val
```

### 3.2. Token Economy
- **Redução de Sintaxe:** Remove aspas, chaves e vírgulas desnecessárias do JSON.
- **Truncamento:** Strings longas limitadas a 1000 chars.
- **Amostragem:** Listas grandes resumidas aos primeiros 5 itens.

### 3.3. Estrutura Padrão
Todo log de aplicaçao deve conter:
- `timestamp`: ISO-8601
- `level`: INFO, ERROR, WARNING
- `name`: Nome do logger (modulo)
- `message`: Mensagem principal
- Campos extras dinâmicos (contexto, job_id, etc.)

### 3.4. Erros e Exceções
Logs de erro devem incluir snapshot do estado (`input_dto`) quando disponível, formatados em TOON para fácil análise pelo agente.

## 4. Estratégia de Implementação

### 4.1. Biblioteca: `python-toon`
Utilizar a biblioteca `python-toon` para encoding.

### 4.2. Classe `ToonFormatter`
Estender `logging.Formatter` para interceptar registros, aplicar regras de economia e converter para TOON.

```python
# app/utils/logger.py
import toon

class ToonFormatter(logging.Formatter):
    def format(self, record):
        data = self.process(record)
        return toon.encode(data)
```

## 5. Plano de Migração
1. Adicionar `python-toon` ao `requirements.txt`.
2. Substituir `LLMFriendlyFormatter` por `ToonFormatter` em `app/utils/logger.py`.
3. Validar saída no terminal (stderr).
4. Remover dependências de `jq` (já que TOON é legível nativamente e não requer formatação extra).
