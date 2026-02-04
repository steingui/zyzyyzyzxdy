from flask import Blueprint, request, current_app
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import joinedload, selectinload

from app.database.async_db import get_async_engine
from app.models import Partida, Evento
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
        # 1. Pagination Parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Max limit protection
        if per_page > 100:
            per_page = 100
            
        # 2. Filtering Parameters
        rodada = request.args.get('rodada', type=int)
        time_id = request.args.get('time_id', type=int)
        
        # 3. Async Database Session
        engine = get_async_engine()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            # 4. Base Query construction
            base_stmt = select(Partida)
            count_stmt = select(func.count()).select_from(Partida)
            
            # Apply Filters
            conditions = []
            if rodada:
                conditions.append(Partida.rodada == rodada)
            if time_id:
                conditions.append(or_(Partida.time_casa_id == time_id, Partida.time_fora_id == time_id))
                
            if conditions:
                base_stmt = base_stmt.where(*conditions)
                count_stmt = count_stmt.where(*conditions)
            
            # 5. Execute Count Query (for Pagination metadata)
            total_result = await session.execute(count_stmt)
            total = total_result.scalar()
            
            # 6. Apply Sorting and Pagination to Main Query
            stmt = base_stmt.order_by(Partida.rodada.desc(), Partida.data_hora.desc())
            stmt = stmt.limit(per_page).offset((page - 1) * per_page)
            
            # 7. Apply Eager Loading (Optimization)
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
            
            # 9. Construct Response
            pagination_obj = AsyncPagination(
                items=partidas,
                page=page,
                per_page=per_page,
                total=total
            )
            
            return ApiResponse.paginate(
                pagination_obj, 
                matches_schema, 
                'matches_v2.get_matches',
                rodada=rodada, # Preserve query params in links
                time_id=time_id
            )

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
