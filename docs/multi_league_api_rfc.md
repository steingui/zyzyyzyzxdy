# RFC-002: Multi-League Support para REST API Endpoints

**Status:** ✅ Implementado  
**Data:** 2026-01-31  
**Prioridade:** Alta  
**Estimativa:** 3-5 dias

---

## 📋 Sumário Executivo

Adaptar os endpoints REST públicos (`/api/matches`, `/api/teams`, `/api/analytics`) para suportar múltiplas ligas através de query parameters opcionais, mantendo compatibilidade retroativa com o comportamento atual (Brasileirão como padrão).

**Motivação:** O backend já suporta multi-league (models `League` e `Season`), mas a API pública ainda está hardcoded para Brasileirão.

---

## 🎯 Objetivos

### Objetivos Primários
1. ✅ Adicionar suporte a `league` e `year` como query parameters em todos endpoints públicos
2. ✅ Manter retrocompatibilidade: sem parâmetros = Brasileirão temporada atual
3. ✅ Validar inputs (league slug, year range)
4. ✅ Atualizar OpenAPI specs (EN/PT)

### Objetivos Secundários
1. Criar endpoint `/api/leagues` para listar ligas disponíveis
2. Criar endpoint `/api/seasons` para listar temporadas por liga
3. Adicionar filtro `league_id` em schemas Marshmallow

---

## 🔍 Análise dos Endpoints Atuais

### 1. `/api/matches` (matches.py)

**Atual:**
```python
@matches_bp.route('/', methods=['GET'])
def get_matches():
    rodada = request.args.get('rodada', type=int)
    time_id = request.args.get('time_id', type=int)
    
    query = Partida.query
    if rodada:
        query = query.filter_by(rodada=rodada)
    if time_id:
        query = query.filter((Partida.time_casa_id == time_id) | 
                            (Partida.time_fora_id == time_id))
```

**Problema:** Não filtra por `season_id`, retorna partidas de TODAS as temporadas.

**Impacto:** Retorna dados misturados de 2024, 2025, 2026... sem distinção.

---

### 2. `/api/teams` (teams.py)

**Atual:**
```python
@teams_bp.route('/', methods=['GET'])
def get_teams():
    times = Time.query.order_by(Time.nome).all()
```

**Problema:** Retorna TODOS os times de TODAS as ligas (Brasileirão + Liga MX + ...).

**Impacto:** Dados irrelevantes para usuários focados em uma liga específica.

---

### 3. `/api/analytics/ranking-xg` (analytics.py)

**Atual:**
```sql
SELECT * FROM v_ranking_xg
```

**Problema:** View hardcoded para Brasileirão no SQL (sem filtro de season).

**Impacto:** Ranking global sem separação por liga/temporada.

---

## 🛠️ Mudanças Propostas

### Fase 1: Core Multi-League Support

#### 1.1 Helper Function (Novo: `app/utils/league_helpers.py`)

```python
from app.models import League, Season
from flask import request, current_app
from datetime import datetime

def get_current_season(league_slug='brasileirao', year=None):
    """
    Resolve league_slug + year para season_id.
    Defaults: league='brasileirao', year=current year
    
    Returns:
        Season object or None
    Raises:
        ValueError: Invalid league or year
    """
    # Get league
    league = League.query.filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"League '{league_slug}' not found")
    
    # Resolve year
    if year is None:
        # Pegar temporada atual da liga
        season = Season.query.filter_by(
            league_id=league.id, 
            is_current=True
        ).first()
    else:
        # Validar range
        current_year = datetime.now().year
        if year < 2020 or year > current_year + 1:
            raise ValueError(f"Year must be between 2020 and {current_year + 1}")
        
        season = Season.query.filter_by(
            league_id=league.id,
            year=year
        ).first()
    
    if not season:
        raise ValueError(f"No season found for {league_slug} {year or 'current'}")
    
    return season

def extract_league_params():
    """
    Extract and validate league/year from request args.
    
    Returns:
        tuple: (season, league_slug, year)
    """
    league_slug = request.args.get('league', 'brasileirao')
    year = request.args.get('year', type=int)
    
    season = get_current_season(league_slug, year)
    
    current_app.logger.info(
        f"Resolved params: league={league_slug}, year={year or 'current'} "
        f"→ season_id={season.id}"
    )
    
    return season, league_slug, year
```

---

#### 1.2 `/api/matches` (Atualizado)

**Novo:**
```python
@matches_bp.route('/', methods=['GET'])
@cache.cached(timeout=1800, query_string=True)
def get_matches():
    try:
        # Extract parameters
        rodada = request.args.get('rodada', type=int)
        time_id = request.args.get('time_id', type=int)
        
        # NEW: Multi-league support
        season, league_slug, year = extract_league_params()
        
        # Validation
        if rodada is not None and (rodada < 1 or rodada > season.league.num_rounds):
            return jsonify({
                "error": f"Invalid rodada: must be between 1 and {season.league.num_rounds}"
            }), 400
        if time_id is not None and time_id < 1:
            return jsonify({"error": "Invalid time_id: must be positive"}), 400
        
        # Query with season filter
        query = Partida.query.filter_by(season_id=season.id)
        
        if rodada:
            query = query.filter_by(rodada=rodada)
        if time_id:
            query = query.filter(
                (Partida.time_casa_id == time_id) | 
                (Partida.time_fora_id == time_id)
            )
        
        partidas = query.order_by(
            Partida.rodada.desc(), 
            Partida.data_hora.desc()
        ).all()
        
        current_app.logger.info(
            f"Fetched {len(partidas)} matches "
            f"(league={league_slug}, year={year}, rodada={rodada}, time_id={time_id})"
        )
        
        return jsonify(matches_schema.dump(partidas))
        
    except ValueError as e:
        # Invalid league/year
        current_app.logger.warning(f"Invalid league params: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching matches: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch matches"}), 500
```

**Query Parameters:**
- `league` (opcional, default: `brasileirao`) - Liga slug (ex: `brasileirao`, `liga-mx`)
- `year` (opcional, default: temporada atual) - Ano da temporada
- `rodada` (opcional) - Rodada específica
- `time_id` (opcional) - Filtrar por time

**Exemplos:**
```bash
# Brasileirão 2026 rodada 1 (padrão)
GET /api/matches?rodada=1

# Liga MX 2025 rodada 10
GET /api/matches?league=liga-mx&year=2025&rodada=10

# Brasileirão 2024 times do Flamengo
GET /api/matches?year=2024&time_id=1
```

---

#### 1.3 `/api/teams` (Atualizado)

**Novo:**
```python
@teams_bp.route('/', methods=['GET'])
@cache.cached(timeout=3600, query_string=True)
def get_teams():
    try:
        # NEW: Multi-league support
        season, league_slug, year = extract_league_params()
        
        # Get active teams for this season
        from app.models import TeamSeason
        
        team_seasons = TeamSeason.query.filter_by(
            season_id=season.id,
            active=True
        ).all()
        
        times = [ts.team for ts in team_seasons]
        
        current_app.logger.info(
            f"Fetched {len(times)} teams for {league_slug} {year or 'current'}"
        )
        
        return jsonify(teams_schema.dump(times))
        
    except ValueError as e:
        current_app.logger.warning(f"Invalid league params: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching teams: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch teams"}), 500
```

**Query Parameters:**
- `league` (opcional, default: `brasileirao`)
- `year` (opcional, default: temporada atual)

**Exemplos:**
```bash
# Times do Brasileirão 2026
GET /api/teams

# Times da Liga MX 2025
GET /api/teams?league=liga-mx&year=2025
```

---

#### 1.4 `/api/analytics/ranking-xg` (Atualizado)

**Novo:**
```python
@analytics_bp.route('/ranking-xg', methods=['GET'])
@cache.cached(timeout=1800, query_string=True)
def get_ranking_xg():
    try:
        # NEW: Multi-league support
        season, league_slug, year = extract_league_params()
        
        # Dynamic query with season filter
        query = sqlalchemy.text("""
            SELECT 
                t.nome as time,
                COUNT(DISTINCT p.id) as jogos,
                AVG(CASE 
                    WHEN p.time_casa_id = t.id THEN ep.xg_casa 
                    WHEN p.time_fora_id = t.id THEN ep.xg_fora 
                END) as xg_favor_medio,
                AVG(CASE 
                    WHEN p.time_casa_id = t.id THEN ep.xg_fora 
                    WHEN p.time_fora_id = t.id THEN ep.xg_casa 
                END) as xg_contra_medio
            FROM times t
            JOIN partidas p ON (p.time_casa_id = t.id OR p.time_fora_id = t.id)
            JOIN estatisticas_partida ep ON ep.partida_id = p.id
            WHERE p.season_id = :season_id AND p.status = 'finished'
            GROUP BY t.id, t.nome
            ORDER BY xg_favor_medio DESC
        """)
        
        result = db.session.execute(query, {"season_id": season.id})
        
        ranking = []
        for row in result:
            ranking.append({
                "team": row.time,
                "matches": row.jogos,
                "avg_xg_for": float(row.xg_favor_medio),
                "avg_xg_against": float(row.xg_contra_medio)
            })
        
        current_app.logger.info(
            f"Ranking xG retrieved: {len(ranking)} teams "
            f"({league_slug} {year or 'current'})"
        )
        
        return jsonify(ranking)
        
    except ValueError as e:
        current_app.logger.warning(f"Invalid league params: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching ranking xG: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch ranking data"}), 500
```

---

### Fase 2: Novos Endpoints de Descoberta

#### 2.1 `/api/leagues` (NOVO)

```python
# app/blueprints/leagues.py (NOVO)
from flask import Blueprint, jsonify, current_app
from app.models import League
from app import cache

leagues_bp = Blueprint('leagues', __name__)

@leagues_bp.route('/', methods=['GET'])
@cache.cached(timeout=7200)  # 2 horas
def get_leagues():
    """List all available leagues"""
    try:
        leagues = League.query.order_by(League.name).all()
        
        result = []
        for league in leagues:
            result.append({
                "id": league.id,
                "name": league.name,
                "slug": league.slug,
                "country": league.country,
                "confederation": league.confederation,
                "num_teams": league.num_teams,
                "num_rounds": league.num_rounds,
                "current_season": league.seasons.filter_by(is_current=True).first().year 
                    if league.seasons.filter_by(is_current=True).first() else None
            })
        
        current_app.logger.info(f"Fetched {len(result)} leagues")
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error fetching leagues: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch leagues"}), 500
```

**Exemplo Response:**
```json
[
  {
    "id": 1,
    "name": "Brasileirão Série A",
    "slug": "brasileirao",
    "country": "Brazil",
    "confederation": "CONMEBOL",
    "num_teams": 20,
    "num_rounds": 38,
    "current_season": 2026
  },
  {
    "id": 2,
    "name": "Liga MX",
    "slug": "liga-mx",
    "country": "Mexico",
    "confederation": "CONCACAF",
    "num_teams": 18,
    "num_rounds": 17,
    "current_season": 2025
  }
]
```

---

#### 2.2 `/api/leagues/<slug>/seasons` (NOVO)

```python
@leagues_bp.route('/<slug>/seasons', methods=['GET'])
@cache.cached(timeout=3600)  # 1 hora
def get_league_seasons(slug):
    """List all seasons for a specific league"""
    try:
        league = League.query.filter_by(slug=slug).first_or_404()
        
        seasons = Season.query.filter_by(league_id=league.id)\
            .order_by(Season.year.desc()).all()
        
        result = []
        for season in seasons:
            result.append({
                "id": season.id,
                "year": season.year,
                "is_current": season.is_current,
                "start_date": season.start_date.isoformat() if season.start_date else None,
                "end_date": season.end_date.isoformat() if season.end_date else None,
                "league": {
                    "id": league.id,
                    "name": league.name,
                    "slug": league.slug
                }
            })
        
        current_app.logger.info(f"Fetched {len(result)} seasons for {slug}")
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error fetching seasons: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch seasons"}), 500
```

**Exemplo:**
```bash
GET /api/leagues/brasileirao/seasons
```

**Response:**
```json
[
  {
    "id": 3,
    "year": 2026,
    "is_current": true,
    "start_date": "2026-01-25",
    "end_date": null,
    "league": {
      "id": 1,
      "name": "Brasileirão Série A",
      "slug": "brasileirao"
    }
  },
  {
    "id": 2,
    "year": 2025,
    "is_current": false,
    "start_date": "2025-04-15",
    "end_date": "2025-12-10",
    "league": {...}
  }
]
```

---

## 📝 OpenAPI Spec Updates

### Exemplo: `/api/matches` (openapi-en.yaml)

```yaml
/api/matches:
  get:
    tags:
      - Matches
    summary: Get list of matches with optional filters
    description: |
      Get matches for a specific league and season.
      Defaults to Brasileirão current season if not specified.
    parameters:
      - name: league
        in: query
        description: League slug (default: brasileirao)
        required: false
        schema:
          type: string
          example: brasileirao
          enum: [brasileirao, liga-mx, superliga-argentina]
      
      - name: year
        in: query
        description: Season year (default: current season)
        required: false
        schema:
          type: integer
          minimum: 2020
          maximum: 2027
          example: 2026
      
      - name: rodada
        in: query
        description: Round/gameweek number
        required: false
        schema:
          type: integer
          minimum: 1
          example: 10
      
      - name: time_id
        in: query
        description: Filter by team ID
        required: false
        schema:
          type: integer
          minimum: 1
          example: 5
    
    responses:
      '200':
        description: List of matches
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: '#/components/schemas/Match'
      
      '400':
        description: Invalid league or year parameter
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
                  example: "League 'invalid-league' not found"
```

---

## 🧪 Testes Necessários

### Unit Tests
```python
# tests/test_multi_league_api.py

def test_matches_default_brasileirao():
    """Should default to Brasileirão current season"""
    response = client.get('/api/matches')
    assert response.status_code == 200
    # Verify all matches are from current Brasileirão season

def test_matches_with_league_param():
    """Should filter by league parameter"""
    response = client.get('/api/matches?league=liga-mx&year=2025')
    assert response.status_code == 200
    # Verify matches are from Liga MX 2025

def test_invalid_league():
    """Should return 400 for invalid league"""
    response = client.get('/api/matches?league=invalid')
    assert response.status_code == 400
    assert 'not found' in response.json['error']

def test_teams_league_filter():
    """Should return only teams from specified league"""
    response = client.get('/api/teams?league=brasileirao&year=2026')
    assert response.status_code == 200
    teams = response.json
    assert all(team['league_id'] == 1 for team in teams)
```

### Integration Tests
```bash
# Manual API tests
curl "http://localhost:5000/api/matches?league=brasileirao&year=2026&rodada=1"
curl "http://localhost:5000/api/teams?league=liga-mx"
curl "http://localhost:5000/api/analytics/ranking-xg?year=2025"
curl "http://localhost:5000/api/leagues"
curl "http://localhost:5000/api/leagues/brasileirao/seasons"
```

---

## 📦 Implementação em Fases

### Fase 1: Core Multi-League (3 dias) - **Prioridade P0**
- [ ] Criar `app/utils/league_helpers.py`
- [ ] Atualizar `/api/matches` com filtro season
- [ ] Atualizar `/api/teams` com filtro season
- [ ] Atualizar `/api/analytics/ranking-xg`
- [ ] Atualizar `/api/analytics/summary`
- [ ] Testes unitários

### Fase 2: Discovery Endpoints (1 dia) - **Prioridade P1**
- [ ] Criar `/api/leagues`
- [ ] Criar `/api/leagues/<slug>/seasons`
- [ ] Testes

### Fase 3: Documentação (1 dia) - **Prioridade P1**
- [ ] Atualizar `openapi-en.yaml`
- [ ] Atualizar `openapi-pt.yaml`
- [ ] Atualizar Postman collection
- [ ] Criar migration guide

---

## 🚨 Breaking Changes

### ⚠️ Nenhum!

**Retrocompatibilidade Garantida:**
- Sem parâmetros → Brasileirão temporada atual (comportamento atual)
- Endpoints não mudam de URL
- Response schemas permanecem iguais

---

## 🔗 Referências

- **Models:** `app/models.py` (League, Season, TeamSeason)
- **Current Endpoints:** `app/blueprints/` (matches, teams, analytics)
- **OpenAPI Spec:** `openapi-en.yaml`, `openapi-pt.yaml`

---

## 💡 Futuras Melhorias (Out of Scope)

- Endpoint `/api/leagues/<slug>/standings` (tabela de classificação)
- Endpoint `/api/leagues/<slug>/top-scorers` (artilheiros)
- Filtro por confederação (`/api/leagues?confederation=CONMEBOL`)
- GraphQL API para queries complexas multi-league

---

**Última Atualização:** 2026-01-31  
**Autor:** BR-Statistics Hub Team
