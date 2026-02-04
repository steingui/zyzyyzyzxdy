# RFC: API v2 - Separação de Contextos e Suporte Multi-Liga

**Status:** 🚧 Proposta  
**Data:** 2026-02-04  
**Autor:** Sistema

---

## 1. Problema

Atualmente, a API mistura endpoints de consumo público (dados de partidas, times) com endpoints operacionais/internos (trigger de scraping, filas). Além disso, os endpoints atuais assumem implicitamente uma única liga/contexto ou exigem IDs numéricos, dificultando a navegação intuitiva por "Brasileirão 2024", "Copa do Brasil 2023", etc.

### Problemas Chave:
1.  **Segurança/Exposição:** Endpoints críticos como `/api/scrape` estão visíveis na documentação pública (Swagger/OpenAPI).
2.  **Navegabilidade:** Endpoints `/matches` filtram apenas por rodada, sem distinguir ano ou campeonato.
3.  **Organização:** Mistura de responsabilidades (Leitura vs. Escrita/Operação).

### Contexto de Negócio (Betting):
O objetivo principal da API é fornecer dados estatísticos relevantes para **apostadores**.
-   Os endpoints devem facilitar a análise de tendências (ex: Over/Under, BTTS, Escanteios).
-   A estrutura deve permitir filtros rápidos por Liga/Temporada para comparar desempenho.

---

## 2. Proposta Arquitetural

Propomos dividir a aplicação em dois grupos lógicos de rotas, cada um com sua própria especificação OpenAPI.

### 2.1. Public API (`/api/v1`)
Focada em **consumo de dados**. Totalmente Read-Only (GET).
-   **Alvo:** Frontend, Mobile Apps, Analistas de Dados.
-   **Autenticação:** Opcional (ou API Key pública).
-   **Rate Limit:** Moderado (ex: 1000/hora).
-   **Spec:** `/openapi-public.yaml`

### 2.2. Internal API (`/internal`)
Focada em **operação e administração**. Trigger de jobs, gestão de cache, admin.
-   **Alvo:** Admin Dashboard, CI/CD, Cron Jobs, Developers.
-   **Autenticação:** Obrigatória (Admin Bearer Token / API Key Privada).
-   **Rate Limit:** Restrito/Custom.
-   **Spec:** `/openapi-internal.yaml`

---

## 3. Redesign dos Endpoints (Multi-Liga)

Todos os endpoints públicos devem suportar filtragem hierárquica por **Liga** e **Temporada**.

### 3.1. Matches (`/api/v1/matches`)

**Query Parameters:**
-   `league` (string, required): Slug da liga (ex: `brasileirao`, `premier-league`).
-   `season` (int, optional): Ano da temporada (ex: `2024`). Default: Ano atual.
-   `round` (int, optional): Número da rodada.
-   `team` (string, optional): Slug ou ID do time.

**Exemplo de Request:**
```http
GET /api/v1/matches?league=brasileirao&season=2024&round=1
```

**Implementation Hook:**
Será necessário fazer JOIN nas tabelas `Partida` -> `Temporada` -> `Liga` para filtrar pelo slug e ano.

### 3.2. Teams (`/api/v1/teams`)

Listar times que participaram de uma liga/temporada específica.

**Query Parameters:**
-   `league` (string, required): Slug da liga.
-   `season` (int, optional): Ano.

**Exemplo:**
```http
GET /api/v1/teams?league=brasileirao&season=2024
```

### 3.3. Analytics (`/api/v1/analytics`)

Endpoints de estatísticas agregadas.

**Exemplo:**
```http
GET /api/v1/analytics/standings?league=brasileirao&season=2024
```

---

## 4. Internal API Endpoints

Os endpoints atuais de scraping serão movidos para o prefixo `/internal`.

-   `POST /internal/scrape/trigger` (antigo `/api/scrape`)
    -   Payload: `{ "league": "brasileirao", "year": 2024, "round": 1 }`
-   `GET /internal/scrape/jobs` (antigo `/api/scrape/jobs`)
-   `GET /internal/scrape/status/{job_id}`
-   `DELETE /internal/cache/flush`

---

## 5. Plano de Migração

1.  **Refatorar Blueprints:**
    -   Renomear `scrape_bp` para `internal_scrape_bp`.
    -   Atualizar `url_prefix` para `/internal/scrape`.
2.  **Atualizar Models/Schemas:**
    -   Garantir que validações aceitem slugs ao invés de apenas IDs.
3.  **Atualizar Queries:**
    -   Refatorar `get_matches` para aceitar `league` e `season`.
    -   Implementar lógica de resolução `Slug -> ID` eficiente (com cache).
4.  **OpenAPI Separation:**
    -   Criar `openapi-internal.yaml`.
    -   Atualizar `openapi-public.yaml` removendo scrape ops.

---

## 6. Otimizações Relacionadas
-   **Cache por Contexto:** As chaves de cache devem incluir `league:season` para evitar colisão.
-   **Indexes:** Garantir índices em `liga.slug` e `temporada.ano`.
