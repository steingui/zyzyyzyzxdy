from flask import Blueprint, request, current_app
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import joinedload, selectinload

from app.database.async_db import get_async_engine
from app.models import Partida, Evento, Liga
from app.blueprints.v2.schemas import PartidaSchema
from app.blueprints.v2.utils import ApiResponse, AsyncPagination

matches_v2_bp = Blueprint('matches_v2', __name__)
match_schema = PartidaSchema()
matches_schema = PartidaSchema(many=True)

@matches_v2_bp.route('/', methods=['GET'])
async def get_matches():
    """
    Get list of matches
    ---
    get:
      tags:
        - Matches
      summary: List matches with pagination
      description: Retrieve a paginated list of matches with optional filtering by round or team.
      parameters:
        - name: league
          in: query
          required: true
          schema:
            type: string
          description: League slug (e.g. 'brasileirao', 'premier-league')
        - name: season
          in: query
          required: true
          schema:
            type: integer
          description: Season year (e.g. 2026)
        - name: page
          in: query
          schema:
            type: integer
            default: 1
          description: Page number
        - name: per_page
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
          description: Items per page
        - name: rodada
          in: query
          schema:
            type: integer
          description: Filter by round number (1-38)
        - name: time_id
          in: query
          schema:
            type: integer
          description: Filter by team ID (home or away)
      responses:
        200:
          description: List of matches
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/Meta'
                  - $ref: '#/components/schemas/Links'
                  - type: object
                    properties:
                      data:
                        type: array
                        items: 
                          $ref: '#/components/schemas/Partida'
        500:
          description: Internal server error
    """
    try:
        # 1. Mandatory Filtering Parameters (RFC 001)
        league_slug = request.args.get('league')
        season = request.args.get('season', type=int)

        if not league_slug or not season:
            return ApiResponse.error(
                "Mandatory parameters missing. You must provide 'league' (slug) and 'season' (year).",
                status_code=400
            )

        # 2. Pagination & Optional Filters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        rodada = request.args.get('rodada', type=int)
        time_id = request.args.get('time_id', type=int)
        
        # Max limit protection
        if per_page > 100: per_page = 100

        # 3. Check Cache
        from app.database.redis import cache
        from flask import jsonify, url_for

        cache_key = f"v2:matches:{league_slug}:{season}:{rodada}:{time_id}:{page}:{per_page}"
        cached_data = cache.get(cache_key)
        if cached_data:
            # Refresh timestamps in meta to show it's a fresh HIT? 
            # Or just return as is. RFC says cache static data.
            # We should probably return a header X-Cache: HIT
            response = jsonify(cached_data)
            response.headers['X-Cache'] = 'HIT'
            return response

        # 4. Async Database Session
        engine = get_async_engine()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            # 4.1 Resolve League Slug -> ID (with Index/Cache)
            # Try cache first for League ID
            liga_cache_key = f"v2:metadata:liga_id:{league_slug}"
            liga_id = cache.get(liga_cache_key)

            if not liga_id:
                stmt_liga = select(Liga.id).where(Liga.slug == league_slug)
                result_liga = await session.execute(stmt_liga)
                liga_id = result_liga.scalar()
                
                if not liga_id:
                    return ApiResponse.error(f"League not found: {league_slug}", status_code=404)
                
                cache.set(liga_cache_key, liga_id, ttl=3600*24) # 24h cache for league ID

            # 4.2 Base Query construction
            base_stmt = select(Partida)
            count_stmt = select(func.count()).select_from(Partida)
            
            # Apply Strict Filters
            conditions = [
                Partida.liga_id == liga_id,
                Partida.ano == season
            ]
            
            # Apply Optional Filters
            if rodada:
                conditions.append(Partida.rodada == rodada)
            if time_id:
                conditions.append(or_(Partida.time_casa_id == time_id, Partida.time_fora_id == time_id))
            
            base_stmt = base_stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
            
            # 5. Execute Count Query (for Pagination metadata)
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0
            
            # 6. Apply Sorting and Pagination
            stmt = base_stmt.order_by(Partida.rodada.desc(), Partida.data_hora.desc())
            stmt = stmt.limit(per_page).offset((page - 1) * per_page)
            
            # 7. Apply Eager Loading
            stmt = stmt.options(
                joinedload(Partida.time_casa),
                joinedload(Partida.time_fora),
                joinedload(Partida.estadio),
                joinedload(Partida.arbitro),
                joinedload(Partida.estatisticas),
                selectinload(Partida.eventos).joinedload(Evento.time),
                selectinload(Partida.eventos).joinedload(Evento.jogador),
                joinedload(Partida.temporada)
            )
            
            # 8. Execute Main Query
            result = await session.execute(stmt)
            partidas = result.scalars().all()
            
            # 9. Construct Response Dict (Manual to support caching)
            from datetime import datetime
            
            pagination_meta = {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page > 0 else 0
            }

            response_payload = {
                "data": matches_schema.dump(partidas),
                "meta": {
                    "pagination": pagination_meta,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "version": "v2.0.0",
                    "filters": {
                        "league": league_slug,
                        "season": season,
                        "round": rodada
                    }
                },
                "links": {} # Links are dynamic, maybe we shouldn't cache links? 
                            # If we cache the dict, links are fixed to the page request. 
                            # It's fine for exact cache usage.
            }
            
            # Generate Links manually or via helper?
            # Let's use the helper logic but implemented here or keep it empty for now 
            # to save complexity, or rely on frontend to build links?
            # Existing API provided links. We should provide them.
            
            endpoint = 'matches_v2.get_matches'
            kwargs = {'league': league_slug, 'season': season}
            if rodada: kwargs['rodada'] = rodada
            if time_id: kwargs['time_id'] = time_id
            if per_page != 20: kwargs['per_page'] = per_page
            
            links = {}
            if page > 1:
                links['prev'] = url_for(endpoint, page=page-1, **kwargs)
            if page < pagination_meta['pages']:
                links['next'] = url_for(endpoint, page=page+1, **kwargs)
            links['self'] = url_for(endpoint, page=page, **kwargs)
            
            response_payload['links'] = links

            # 10. Cache & Return
            # Cache duration: 1 hour for now
            cache.set(cache_key, response_payload, ttl=3600)
            
            response = jsonify(response_payload)
            response.headers['X-Cache'] = 'MISS'
            return response

    except Exception as e:
        current_app.logger.error(f"Error fetching matches v2: {e}", exc_info=True)
        return ApiResponse.error(str(e), status_code=500)

@matches_v2_bp.route('/<int:match_id>', methods=['GET'])
async def get_match(match_id):
    """
    Get match details
    ---
    get:
      tags:
        - Matches
      summary: Get match details
      description: Retrieve detailed information about a specific match.
      parameters:
        - name: match_id
          in: path
          required: true
          schema:
            type: integer
          description: Unique match identifier
      responses:
        200:
          description: Match details
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/Meta'
                  - $ref: '#/components/schemas/Links'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/Partida'
        404:
          description: Match not found
    """
    try:
        engine = get_async_engine()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            stmt = select(Partida).options(
                joinedload(Partida.time_casa),
                joinedload(Partida.time_fora),
                joinedload(Partida.estadio),
                joinedload(Partida.arbitro),
                joinedload(Partida.estatisticas),
                selectinload(Partida.eventos).joinedload(Evento.time),
                selectinload(Partida.eventos).joinedload(Evento.jogador),
                joinedload(Partida.temporada)
            ).filter_by(id=match_id)
            
            result = await session.execute(stmt)
            partida = result.scalars().first()
            
            if not partida:
                return ApiResponse.error("Match not found", code="NOT_FOUND", status_code=404)
                
            return ApiResponse.success(match_schema.dump(partida))
            
    except Exception as e:
        current_app.logger.error(f"Error fetching match v2 {match_id}: {e}", exc_info=True)
        return ApiResponse.error("Internal Server Error", status_code=500)
