# 📚 Documentação BR-Statistics Hub

Documentação técnica do projeto BR-Statistics Hub API.

---

## 📖 Índice

### 🎯 Planejamento & Design

- **[RFC-001: Otimizações da Codebase](optimization_rfc.md)** - Proposta completa de melhorias de performance, escalabilidade e arquitetura (18 otimizações catalogadas)
- **[RFC-002: Multi-League API Support](multi_league_api_rfc.md)** - Adaptação dos endpoints REST para suportar múltiplas ligas via query parameters

### 📋 Padrões & Guias

- **[Padrões de Extração de Dados](DATA_EXTRACTION_STANDARDS.md)** - Guidelines para scraping e normalização de dados

---

## 🚀 RFCs & Propostas

### RFC-001: Otimizações da Codebase
**Status:** Proposta | **Data:** 2026-01-31 | **Prioridade:** Alta

Propõe 18 otimizações organizadas em 3 fases:

**Fase 1 - Quick Wins (1-2 semanas):**
- N+1 Queries Fix
- Connection Pool Tuning
- Redis Cache Layer
- Database Indexing

**ROI Esperado:** 50% melhoria de performance

**Fase 2 - Fundação (3-4 semanas):**
- Async SQLAlchemy
- Celery Worker System
- Redis Job Storage
- API Rate Limiting

**ROI Esperado:** 200% melhoria + escalabilidade horizontal

**Fase 3 - Maturidade (2 meses):**
- OpenTelemetry Tracing
- Feature Flags
- Secrets Management
- Table Partitioning

**ROI Esperado:** Produção enterprise-ready

[📄 Ver RFC Completa](optimization_rfc.md)

---

### RFC-002: Multi-League API Support
**Status:** Proposta | **Data:** 2026-01-31 | **Prioridade:** Alta  
**Estimativa:** 3-5 dias

Adapta endpoints REST públicos para suportar múltiplas ligas:

**Mudanças Principais:**
- ✅ Query params `league` e `year` em todos endpoints
- ✅ Retrocompatível (default: Brasileirão atual)
- ✅ Novos endpoints `/api/leagues` e `/api/leagues/<slug>/seasons`
- ✅ Helper function `extract_league_params()`

**Endpoints Afetados:**
- `/api/matches` - filtro por season_id
- `/api/teams` - via TeamSeason join
- `/api/analytics/*` - queries dinâmicas

**Fase 1 (3 dias):** Core multi-league support  
**Fase 2 (1 dia):** Discovery endpoints  
**Fase 3 (1 dia):** Documentação OpenAPI

[📄 Ver RFC Completa](multi_league_api_rfc.md)

---

## 🏗️ Arquitetura

### Componentes Principais

```
┌─────────────────┐
│   Flask API     │  ← REST endpoints
├─────────────────┤
│  Queue Worker   │  ← Background scraping
├─────────────────┤
│   PostgreSQL    │  ← Data storage
├─────────────────┤
│   Playwright    │  ← Web scraping
└─────────────────┘
```

### Tecnologias

- **Backend:** Flask, SQLAlchemy, Marshmallow
- **Database:** PostgreSQL (Render)
- **Scraping:** Playwright, BeautifulSoup
- **Queue:** Python threading.Queue (→ Celery proposto)
- **Docs:** OpenAPI/Swagger UI

---

## 📊 Performance Metrics (Baseline)

| Métrica | Valor Atual | Meta (Pós-Otimização) |
|---------|-------------|----------------------|
| API Response Time | ~500ms | ~50ms |
| Scraping Round | ~3-4min | ~2min |
| DB Queries/Request | 4+ (N+1) | 1 |
| Cache Hit Rate | 0% | 90% |
| Concurrent Jobs | 1 | 10+ |

---

## 🔗 Links Úteis

- [OpenAPI Spec (EN)](../openapi-en.yaml)
- [OpenAPI Spec (PT)](../openapi-pt.yaml)
- [Postman Collection](../br_stats_hub_postman_collection.json)
- [GitHub Repository](https://github.com/steingui/br-estatistics-openclaw) *(your repo)*

---

## 📝 Como Contribuir

1. Leia a RFC relevante
2. Crie uma branch: `feature/rfc-001-cache-layer`
3. Implemente com testes
4. Documente as mudanças
5. Abra PR com referência à RFC

---

**Última Atualização:** 2026-01-31
