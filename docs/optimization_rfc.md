# RFC: Otimizações da Codebase BR-Statistics Hub

**Status:** Em Implementação (Parcialmente Concluído)
**Data:** 2026-01-31  
**Autor:** Sistema  

---

## 📋 Sumário Executivo

Este documento propõe otimizações críticas e incrementais para a codebase do BR-Statistics Hub, focando em **performance**, **escalabilidade**, **segurança** e **manutenibilidade**.

---

## 🎯 Otimizações Críticas (Alta Prioridade)

### 1. **Substituir JSON File Storage por Redis**

**Problema:** `data/scrape_jobs.json` não é thread-safe e não escala

**Proposta:**
```python
# Antes: app/routes/scrape.py
jobs = json.load(open(JOBS_FILE))  # Race condition!

# Depois: Redis
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
r.hset('jobs', job_id, json.dumps(job_data))
```

**Benefícios:**
- ✅ Thread-safe (operações atômicas)
- ✅ Pub/Sub para notificações em tempo real
- ✅ TTL automático para limpeza de jobs antigos
- ✅ Suporta múltiplas instâncias da API

**Esforço:** 4h | **ROI:** Alto

---

### 2. **Async Database Queries com SQLAlchemy + asyncpg** (✅ IMPLEMENTADO v3.4.0)

**Problema:** Queries síncronas bloqueiam o event loop do Flask

**Proposta:**
```python
# Antes: app/routes/matches.py
matches = Partida.query.filter_by(rodada=round_num).all()  # Blocking!

# Depois: Async
from sqlalchemy.ext.asyncio import AsyncSession
async def get_matches(round_num: int):
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Partida).where(Partida.rodada == round_num)
        )
        return result.scalars().all()
```

**Benefícios:**
- ✅ Melhor throughput da API (10-50x mais requests/segundo)
- ✅ Reduz latência de I/O
- ✅ Permite conexões persistentes

**Esforço:** 8h | **ROI:** Muito Alto

---

### 3. **Implementar Cache Layer (Redis)** (✅ IMPLEMENTADO v3.3.0)

**Problema:** Queries repetitivas sem cache

**Proposta:**
```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/1',
    'CACHE_DEFAULT_TIMEOUT': 300
})

@app.route('/api/teams')
@cache.cached(timeout=3600, query_string=True)
def list_teams():
    return Team.query.all()
```

**Benefícios:**
- ✅ Reduz carga no PostgreSQL (90%)
- ✅ Resposta API: 500ms → 5ms
- ✅ Cache invalidation automático

**Esforço:** 3h | **ROI:** Muito Alto

---

### 4. **N+1 Queries - Eager Loading** (✅ IMPLEMENTADO v3.4.0)

**Problema:** Queries N+1 em `/api/matches/{id}`

**Análise:**
```python
# Antes (N+1):
match = Partida.query.get(1)  # 1 query
match.time_casa.nome          # +1 query
match.time_fora.nome          # +1 query
match.estadio.nome            # +1 query
# Total: 4 queries para 1 partida!

# Depois (Eager Loading):
match = Partida.query.options(
    joinedload(Partida.time_casa),
    joinedload(Partida.time_fora),
    joinedload(Partida.estadio)
).get(1)
# Total: 1 query!
```

**Benefícios:**
- ✅ Reduz latência: 200ms → 20ms
- ✅ Menos overhead de rede DB

**Esforço:** 2h | **ROI:** Alto

---

### 5. **Idempotent Scraping Jobs** (✅ IMPLEMENTADO v3.1.0)

**Problema:** `is_duplicate` verifica PIDs que podem ser reciclados

**Proposta:**
```python
# Antes:
if is_process_running(job['pid']):  # PID pode ser reciclado!
    return 409

# Depois: UUID + Lock semântico
import uuid
job_key = f"{league}:{year}:{round}"
if r.set(f"lock:{job_key}", uuid.uuid4(), nx=True, ex=3600):
    # Acquired lock, pode processar
else:
    return 409, "Job already processing"
```

**Benefícios:**
- ✅ Evita duplicatas reais
- ✅ Lock distribuído (múltiplas instâncias)
- ✅ TTL automático (self-healing)

**Esforço:** 2h | **ROI:** Médio

---

## 🔧 Otimizações de Performance (Média Prioridade)

### 6. **Connection Pool Tuning** (✅ IMPLEMENTADO v3.1.0)

**Proposta:**
```python
# config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,          # Antes: 5
    'max_overflow': 40,       # Antes: 10
    'pool_pre_ping': True,    # Health check
    'pool_recycle': 3600      # Evita conexões stale
}
```

**Benefícios:**
- ✅ Reduz latência de conexão
- ✅ Suporta mais requisições simultâneas

**Esforço:** 0.5h | **ROI:** Médio

---

### 7. **Scraper: Rate Limiting Inteligente**

**Problema:** Delays fixos (2s) são ineficientes

**Proposta:**
```python
# Antes:
time.sleep(2)  # Sempre 2s, mesmo se site está rápido

# Depois: Adaptive throttling
class AdaptiveThrottle:
    def __init__(self, min_delay=0.5, max_delay=5):
        self.delays = deque(maxlen=10)
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    def wait(self, response_time):
        # Se site está lento, diminui velocidade
        delay = max(self.min_delay, min(response_time * 1.5, self.max_delay))
        time.sleep(delay)
        self.delays.append(delay)
```

**Benefícios:**
- ✅ Scraping 30-50% mais rápido quando possível
- ✅ Respeita limites do servidor (não sobrecarrega)

**Esforço:** 3h | **ROI:** Médio

---

### 8. **Playwright: Reutilizar Browser Context**

**Problema:** `browser.launch()` a cada partida (lento!)

**Proposta:**
```python
# Antes:
with sync_playwright() as p:
    browser = p.chromium.launch()  # 2-3s CADA vez!
    page = browser.new_page()
    
# Depois: Persistent context
@contextmanager
def get_browser_pool():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()

# Reutiliza browser para todas as partidas da rodada
with get_browser_pool() as browser:
    for url in match_urls:
        page = browser.new_page()
        scrape_match(page, url)
        page.close()
```

**Benefícios:**
- ✅ Reduz overhead: ~30s por rodada
- ✅ Menos uso de memória

**Esforço:** 2h | **ROI:** Alto

---

## 🛡️ Otimizações de Segurança

### 9. **Rate Limiting por IP/User**

**Problema:** Flask-Limiter configurado, mas não aplicado em scraping endpoints

**Proposta:**
```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)

@scrape_bp.route('', methods=['POST'])
@limiter.limit("5 per minute")  # Previne spam
def start_scrape():
    ...
```

**Esforço:** 1h | **ROI:** Médio

---

### 10. **Secrets Management**

**Problema:** `.env` commitado em alguns casos

**Proposta:**
```bash
# Docker Secrets / Kubernetes Secrets
docker secret create db_url postgres://...

# Ou: HashiCorp Vault
vault kv put secret/br-stats DATABASE_URL=...
```

**Esforço:** 4h | **ROI:** Alto (Compliance)

---

## 📊 Otimizações de Arquitetura

### 11. **Event-Driven Architecture (Webhook Notifications)**

**Proposta:**
```python
# Quando job completa, dispara webhook
requests.post(
    webhook_url,
    json={
        'event': 'scrape.completed',
        'job_id': job_id,
        'matches_scraped': 10
    }
)
```

**Benefícios:**
- ✅ Integração com CI/CD
- ✅ Notificações em tempo real
- ✅ Extensibilidade

**Esforço:** 5h | **ROI:** Médio

---

### 12. **Separar Worker em Processo Independente (Celery)**

**Problema:** Worker thread compartilha memória com API

**Proposta:**
```python
# worker.py (processo separado)
from celery import Celery

app = Celery('scraper', broker='redis://localhost:6379/0')

@app.task
def scrape_job(league, year, round):
    run_batch(league, year, round)

# api.py
@scrape_bp.route('', methods=['POST'])
def start_scrape():
    task = scrape_job.delay(league, year, round)
    return jsonify({'task_id': task.id}), 202
```

**Benefícios:**
- ✅ Isolamento de falhas (worker crash ≠ API crash)
- ✅ Escalabilidade horizontal (múltiplos workers)
- ✅ Retry automático (Celery built-in)
- ✅ Monitoring (Flower dashboard)

**Esforço:** 8h | **ROI:** Muito Alto

---

### 13. **Feature Flags (LaunchDarkly / Unleash)**

**Proposta:**
```python
from unleash import UnleashClient

client = UnleashClient(url="http://unleash:4242", app_name="br-stats")

if client.is_enabled("new_scraper_v2"):
    scraper = NewScraperV2()
else:
    scraper = OldScraper()
```

**Benefícios:**
- ✅ Deploy confiante (rollback fácil)
- ✅ A/B testing
- ✅ Canary releases

**Esforço:** 6h | **ROI:** Médio

---

## 🧪 Otimizações de Testes

### 14. **VCR.py para Testes de Scraper**

**Problema:** Testes de scraper dependem de site externo

**Proposta:**
```python
import vcr

@vcr.use_cassette('fixtures/match_123.yaml')
def test_scrape_match():
    data = scraper.scrape('https://ogol.com.br/jogo/...')
    assert data['home_team'] == 'Flamengo'
```

**Benefícios:**
- ✅ Testes determinísticos
- ✅ CI/CD não depende de ogol.com.br
- ✅ Mais rápido (sem rede)

**Esforço:** 4h | **ROI:** Alto

---

## 📈 Otimizações de Observabilidade

### 15. **OpenTelemetry + Jaeger**

**Proposta:**
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("scrape_match")
def scrape_match(url):
    with tracer.start_as_current_span("fetch_page"):
        page.goto(url)
    with tracer.start_as_current_span("extract_data"):
        data = extract_match_info(page)
```

**Benefícios:**
- ✅ Identifica gargalos (tracing distribuído)
- ✅ Correlação de logs
- ✅ SLA monitoring

**Esforço:** 6h | **ROI:** Alto

---

### 16. **Prometheus Metrics**

**Proposta:**
```python
from prometheus_client import Counter, Histogram

scrape_duration = Histogram('scrape_duration_seconds', 'Scraping duration')
scrape_errors = Counter('scrape_errors_total', 'Total scraping errors')

@scrape_duration.time()
def scrape_match(url):
    try:
        ...
    except Exception:
        scrape_errors.inc()
        raise
```

**Benefícios:**
- ✅ Alertas (Grafana)
- ✅ SLO/SLI tracking
- ✅ Capacity planning

**Esforço:** 4h | **ROI:** Alto

---

## 🗂️ Otimizações de DB Schema

### 17. **Indexação Otimizada**

**Análise:**
```sql
-- Adicionar índices compostos estratégicos
CREATE INDEX idx_partidas_season_round ON partidas(season_id, rodada);
CREATE INDEX idx_partidas_teams ON partidas(time_casa_id, time_fora_id);
CREATE INDEX idx_team_seasons_lookup ON team_seasons(team_id, season_id);

-- Índice parcial para queries comuns
CREATE INDEX idx_active_seasons ON seasons(league_id) WHERE is_current = true;
```

**Benefícios:**
- ✅ Query speed: 500ms → 20ms
- ✅ Suporta mais filtros simultâneos

**Esforço:** 2h | **ROI:** Alto

---

### 18. **Particionamento de Tabela `partidas`**

**Proposta:**
```sql
-- Particionar por season_id
CREATE TABLE partidas_2024 PARTITION OF partidas
    FOR VALUES IN (1, 2, 3);  -- season_ids de 2024

CREATE TABLE partidas_2025 PARTITION OF partidas
    FOR VALUES IN (4, 5, 6);  -- season_ids de 2025
```

**Benefícios:**
- ✅ Queries 3-5x mais rápidas (partition pruning)
- ✅ Backup/restore mais rápido
- ✅ DELETE old data mais eficiente

**Esforço:** 6h | **ROI:** Médio (escala futura)

---

## 📦 Roadmap Sugerido

### **Fase 1 - Quick Wins (1-2 semanas)**
1. ✅ N+1 Queries (Eager Loading)
2. ✅ Connection Pool Tuning
3. ✅ Cache Layer (Redis)
4. ✅ Indexação DB

**ROI:** 50% melhoria de performance

### **Fase 2 - Fundação (3-4 semanas)**
1. ✅ Async SQLAlchemy
2. ✅ Celery Worker
3. ✅ Redis Job Storage (Completed)
4. ✅ Rate Limiting

**ROI:** 200% melhoria + escalabilidade horizontal

### **Fase 3 - Maturidade (2 meses)**
1. ✅ OpenTelemetry
2. ✅ Feature Flags
3. ✅ Secrets Management
4. ✅ Table Partitioning

**ROI:** Produção enterprise-ready

---

## 💰 Análise de Custo-Benefício

| Otimização | Esforço | ROI | Prioridade |
|------------|---------|-----|------------|
| Cache Layer | 3h | 🔥 Muito Alto | P0 |
| Async DB | 8h | 🔥 Muito Alto | P0 |
| N+1 Queries | 2h | 🔥 Alto | P0 |
| Celery Worker | 8h | 🔥 Muito Alto | P1 |
| Redis Jobs | 4h | 🔥 Alto | P1 |
| Indexação DB | 2h | 🔥 Alto | P1 |
| Browser Pool | 2h | 🔥 Alto | P2 |
| OpenTelemetry | 6h | Alto | P2 |
| Partitioning | 6h | Médio | P3 |

---

## 🎬 Próximos Passos

1. **Review desta RFC** com equipe
2. **Priorizar itens** (voting)
3. **Criar issues** no GitHub
4. **PoC de Async SQLAlchemy** (validar benefícios)
5. **Implementar Fase 1** (quick wins)

---

## 📚 Referências

- [Flask Performance Best Practices](https://flask.palletsprojects.com/en/latest/deploying/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [PostgreSQL Indexing](https://www.postgresql.org/docs/current/indexes.html)
