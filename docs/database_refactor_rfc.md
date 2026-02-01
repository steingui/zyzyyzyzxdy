# RFC: Database Schema Standardization and Optimization

**Status:** Proposta  
**Data:** 2026-01-31  
**Autor:** Antigravity (Assistant)

---

## 📋 Sumário Executivo

Propomos uma refatoração do esquema do banco de dados para padronizar a nomenclatura das tabelas para o Português (seguindo a convenção majoritária do projeto) e otimizar a performance das consultas do feed de partidas através de um índice composto. Além disso, identificamos e propomos a correção de inconsistências de dados nas ligas recém-adicionadas.

---

## 🎯 Objetivos

1. **Padronização de Nomenclatura**: Migrar tabelas em Inglês (`leagues`, `seasons`) e inconsistentes (`estatisticas_partida`) para o padrão Português Plural.
2. **Otimização de Performance**: Implementar um índice composto na tabela `partidas` para acelerar o dashboard principal.
3. **Coerência de Dados**: Garantir que todos os times estejam corretamente vinculados às suas ligas originais na tabela `times`.

---

## 🔍 Análise de Impacto

### 1. Mudanças de Nomenclatura

| Nome Atual | Novo Nome | Impacto |
| :--- | :--- | :--- |
| `leagues` | `ligas` | Alta - Requer atualização em `models.py` e relacionamentos. |
| `seasons` | `temporadas` | Alta - Relacionamentos em `partidas`, `team_seasons`, etc. |
| `estatisticas_partida` | `estatisticas_partidas` | Média - Tabela 1:1 com `partidas`. |
| `team_seasons` | `times_temporadas` | Média - Tabela de junção. |

### 2. Otimização (Índice Composto)

**Proposta:**
```sql
CREATE INDEX idx_partidas_dashboard_v2 
ON partidas (season_id, status, data_hora DESC) 
INCLUDE (id, time_casa_id, time_fora_id, gols_casa, gols_fora);
```

**Benefício:** Permite **Index Only Scans** para a listagem de partidas por rodada/status, reduzindo drasticamente o I/O no banco de dados.

### 3. Coerência de Dados (Findings)

Identificamos que:
- **Premier League (slug: premier-league)**: Possui 20 partidas gravadas, mas **0 times** vinculados via `league_id` na tabela `times`.
- **Brasileirão (slug: brasileirao)**: Coerente com todos os 20 times vinculados.

---

## 🛠️ Plano de Implementação

### Fase 1: Migração de Estrutura (Alembic)
1. Gerar script de migração para renomear tabelas.
2. Atualizar todas as Foreign Keys e Constraints associadas.

### Fase 2: Atualização do Código
1. Atualizar `app/models.py` com os novos `__tablename__`.
2. Revisar Blueprints (`matches.py`, `teams.py`, `analytics.py`) para garantir compatibilidade.
3. Atualizar o Scraper (`scripts/run_batch.py` e `scripts/db_importer.py`) para utilizar os novos nomes caso haja SQL bruto (atualmente usa ORM).

### Fase 3: Correção de Dados
Executar script de backfill para vincular os times da Premier League à liga correta:
```sql
UPDATE times 
SET league_id = (SELECT id FROM ligas WHERE slug = 'premier-league')
WHERE id IN (
    SELECT DISTINCT time_casa_id FROM partidas 
    WHERE season_id = (SELECT id FROM temporadas WHERE league_id = (SELECT id FROM ligas WHERE slug = 'premier-league'))
);
```

---

## ⚠️ Riscos e Considerações

- **Breaking Changes**: Esta mudança altera nomes de tabelas físicos. Queries manuais ou coleções do Postman que usem SQL direto precisarão de atualização.
- **Down-time**: Requer uma breve pausa na API para executar a migração de renomear tabelas de volume alto (como `partidas` e `estatisticas`).

---

**Aprovação Necessária:**
- [ ] Confirmação dos nomes sugeridos (`ligas`, `temporadas`, `times_temporadas`).
- [ ] Validação do plano de migração.
