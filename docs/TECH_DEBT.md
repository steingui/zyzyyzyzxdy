# Mapa de Débito Técnico

Este documento lista itens de débito técnico identificados que não foram removidos imediatamente, mas devem ser monitorados ou refatorados futuramente.

## 1. Scripts de Migração
- **Arquivo:** `scripts/run_migration.py` e `scripts/migrate.sh`
- **Status:** Duplicação potencial
- **Descrição:** O projeto utiliza `Flask-Migrate` (Alembic) para gerenciamento de migrações (`flask db upgrade`). O script manual `run_migration.py` executa arquivos SQL puros (`database/migrations/*.sql`).
- **Ação Recomendada:** Consolidar todas as migrações no Alembic e remover os scripts manuais assim que confirmar que não há dependências de infraestrutura legada.

## 2. Hardcoded Values
- **Arquivo:** `scripts/crawl_round.py` (e outros)
- **Status:** Atenção necessária
- **Descrição:** Verificar se ainda existem URLs ou anos hardcoded (ex: `/2026/`) fora das configurações passadas via argumento. O refactor Multi-League diminuiu isso, mas vale revisão periódica.

## 3. Testes Automatizados
- **Arquivo:** `scripts/test_extraction.py`, `scripts/test_main.py`
- **Status:** Desatualizados
- **Descrição:** Os scripts de teste na pasta `scripts/` podem não refletir as mudanças recentes na arquitetura (Redis, TOON Logs).
- **Ação:** Mover para suíte de testes oficial (`tests/`) e atualizar, ou remover se redundante.

## 4. Legado de Logging
- **Arquivo:** `app/utils/logger.py`
- **Status:** Monitorar
- **Descrição:** A classe `ToonFormatter` foi implementada recentemente. Verificar se algum módulo ainda está instanciando loggers de forma não padronizada (usando `logging` direto sem passar pela factory `get_logger`).
