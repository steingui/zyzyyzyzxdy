# DBA Schema Analysis Report
**Date:** 2026-01-31  
**Author:** Antigravity (Senior DBA Agent)  
**Database:** Postgres (Render)

## 1. Executive Summary
The database schema is **robust, well-normalized (3NF), and technically sound**. It correctly implements advanced constraints (Unique Keys, Foreign Keys) to guarantee data integrity.

**Score: A-**

Key strengths:
- ✅ Strict Referential Integrity (Foreign Keys everywhere).
- ✅ Correct use of composite Unique Constraints (avoiding duplicates).
- ✅ Optimal Data Types (`JSONB` for flexibility, `NUMERIC` for precise stats).
- ✅ Multi-league architecture supported by design.

Key areas for improvement:
- ⚠️ Naming inconsistency (`plural` vs `singular`).
- ⚠️ Potential redundancy in `Times.league_id`.
- ⚠️ Missing constraints on cross-league consistency.

---

## 2. Detailed Analysis

### 2.1 Consistency & Integrity (Integridade Referencial)
The schema enforces integrity strictly at the database level, which is excellent.

- **`team_seasons`**:  
  `UNIQUE(team_id, season_id)` constraint ensures a team cannot appear twice in the same season table.
  
- **`partidas`**:  
  `UNIQUE(season_id, rodada, time_casa_id, time_fora_id)` ensures the same match isn't recorded twice.
  
- **`estatisticas_partida`**:  
  `UNIQUE(partida_id)` effectively enforces a 1:1 relationship with `partidas`.
  *Note: The table has its own `id` PK, which is technically redundant but harmless.*

### 2.2 Normalization (Normalização)
The schema primarily follows **3rd Normal Form (3NF)**.

- **Teams vs Leagues**:
  - `Times` table has a `league_id` column.
  - `TeamSeason` table is the joining entity for League/Season/Team.
  - **Critique:** `Times.league_id` effectively denormalizes "Current League". If a team is relegated, this column must be updated along with inserting a new `TeamSeason` row. This creates a risk of data anomaly if they drift apart.
  - **Recommendation:** Keep it for performance (fast lookup of current league) but ensure application logic updates it transactionally.

- **Orphaned Entities**:
  - `league_id` in `times` is `NULLABLE`. This is correct (a team might not be in an active tracking league currently).

### 2.3 Coherence & Naming (Nomenclatura)
There are minor inconsistencies in naming conventions:

| Entity | Table Name | Convention | Status |
| :--- | :--- | :--- | :--- |
| Team | `times` | Plural (PT) | ✅ |
| Match | `partidas` | Plural (PT) | ✅ |
| Event | `eventos` | Plural (PT) | ✅ |
| Player | `jogadores` | Plural (PT) | ✅ |
| League | `leagues` | Plural (EN) | ⚠️ Mixed Lang |
| Season | `seasons` | Plural (EN) | ⚠️ Mixed Lang |
| MatchStats | `estatisticas_partida` | **Singular** (PT) | ⚠️ Inconsistent |

**Recommendation:** Standardize on either English or Portuguese. Given the domain (Brasileirão), Portuguese is prevalent, but `leagues/seasons` breaks this. Ideally: `ligas`, `temporadas`, `estatisticas_partidas`.

### 2.4 Indexing & Performance
Indexing strategy is generally good but has room for "Covering Indexes".

- **Good:**
  - `idx_partidas_season`: `(season_id, rodada)` - Perfect for filtering matches by round.
  - `idx_times_nome_trgm`: Trigram index for fuzzy text search on team names. Excellent.
  - `idx_estatisticas_xg`: Useful for analytics queries sorting by xG.

- **Missing/Optimization:**
  - `partidas`: Queries often filter by `status`. `idx_partidas_status` exists but is low cardinality. Likely ignored by query planner unless combined.
  - **Composite Index Opportunity:** `CREATE INDEX idx_partidas_composite ON partidas (season_id, status, data_hora) INCLUDE (id, time_casa_id, time_fora_id);` — This would allow "Index Only Scans" for the dashboard feed.

### 2.5 Scalability
- **JSONB Usage**: `metadata` column in all tables allows schema evolution without migrating tables. This is a "Senior" design choice that pays off for scraping projects where source fields change often.
- **Partitioning**: Not yet implemented. As `estatisticas_partida` grows (approx 1KB per row), millions of matches could slow down.
  - *Mitigation*: Partition `partidas` and `estatisticas_partida` by `season_id` (YearList partitioning).

---

## 3. Conclusion
The schema is "Production Grade". It avoids common pitfalls (like lack of unique constraints) and prepares for complexity (Multi-League). The inconsistencies found are cosmetic (naming) or pragmatic trade-offs (denormalization).

**Action Items:**
1.  [Low] Rename `estatisticas_partida` to `estatisticas_partidas` for consistency.
2.  [Medium] Add composite index on `partidas` for dashboard performance.
3.  [Info] Monitor `Times.league_id` vs `TeamSeason` drift.
