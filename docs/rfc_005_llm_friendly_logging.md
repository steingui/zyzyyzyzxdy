# RFC 005: Padronização de logs amigáveis para LLM

**Status:** ✅ Implementado

## 1. Contexto
Os logs atuais da aplicação são otimizados para leitura humana via terminal (baseados em texto, vário formatos). No entanto, ao solicitar a uma LLM (como agentes de execução ou chatbots) para solucionar problemas, texto não estruturado requer análise extensiva e frequentemente carece de contexto (variáveis de estado, DTOs) necessários para análise de causa raiz.

## 2. Objetivo
Padronizar logs em toda a aplicação (`app/`, `scripts/`) para serem **estruturados** e **nativos para LLM**, maximizando a capacidade de agentes de IA diagnosticarem problemas autonomamente sem chamadas excessivas de ferramentas ou suposições.

## 3. Princípios

### 3.1. JSON Estruturado por Padrão
Logs de texto (`INFO - Processando partida`) são ambíguos. Logs JSON permitem análise direta em objetos.
*Formato Alvo:*
```json
{
  "timestamp": "2026-02-02T22:00:00Z",
  "level": "INFO",
  "service": "api",
  "module": "app.routes.scrape",
  "message": "Trabalho de scraping enfileirado",
  "context": {
    "job_id": "scrape_br_2026_1_12345",
    "league": "brasileirao",
    "round": 1
  }
}
```

### 3.2. Propagação de Contexto (Rastreabilidade)
Cada linha de log deve carregar um `correlation_id` ou `job_id` se fizer parte de um fluxo de trabalho.
- **Requisições HTTP**: Gerar um `request_id` no ponto de entrada.
- **Trabalhos em Segundo Plano**: Herdar `request_id` ou gerar um `job_id`.

### 3.3. "Snapshot de Estado" em Erro
Quando uma exceção ocorre, o log DEVE incluir o "DTO de Estado" — as variáveis locais ou estruturas de dados relevantes sendo processadas, **sanitizadas** de PII/Segredos.
*Em vez de apenas:* `KeyError: 'stats'`
*Log:*
```json
{
  "level": "ERROR",
  "message": "Falha ao extrair estatísticas da partida",
  "error_type": "KeyError",
  "error_detail": "'stats'",
  "input_dto": {
    "match_url": "https://ogol.../123",
    "html_snippet": "div class='box'..." 
  }
}
```

### 3.4. Agrupamento de Logs para Alto Volume
Para loops (ex: crawler iterando 100 links), evitar 1 log por iteração se possível, ou usar um log de "Resumo" no final. No entanto, para depurar erros fatais, logs individuais são preferidos.
*Recomendação:* Manter logs granulares, mas garantir que sejam filtráveis por `job_id`.

### 3.5. Economia de Tokens (Token Economy)
Como esses logs serão consumidos por LLMs, a verbosidade custa caro e pode estourar a janela de contexto.
- **Chaves Concisas**: Evitar aninhamento profundo desnecessário.
- **Truncamento Inteligente**: Strings longas (como HTML ou stacktraces repetitivos) devem ser truncadas (ex: `html_snippet: "<div...>... (truncated 5000 chars)"`).
- **Remoção de Ruído**: Campos `None` ou vazios devem ser omitidos do JSON final.
- **Compressão de Listas**: Em vez de `["item1", "item2", ... "item100"]`, logar `items_count: 100` e uma amostra `items_sample: ["item1", ...]`.

## 4. Estratégia de Implementação

### 4.1. Biblioteca: `python-json-logger`
Substituir formatadores de texto padrão por `jsonlogger.JsonFormatter`.

### 4.2. Configuração de Logger Padrão
Criar um módulo central `app.utils.logger` que retorna uma instância de logger configurada.

```python
# uso
from app.utils.logger import get_logger
logger = get_logger(__name__)

logger.info("Processando Rodada", extra={"round": 5, "league": "fr-1"})
```

### 4.3. Decoradores para Log de DTO
Criar um decorador `@log_context` que captura automaticamente argumentos de entrada e os loga se uma exceção for levantada.

## 5. Plano de Migração
1. Instalar `python-json-logger`.
2. Implementar `app/utils/logger.py`.
3. Refatorar `app/__init__.py` para usar nova configuração.
4. Refatorar `scripts/*.py` para usar novo logger.
5. Atualizar `docker-compose` para encaminhar logs para um arquivo centralizado ou stdout para coleta.
