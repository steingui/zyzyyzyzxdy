from flask import Blueprint, jsonify, request, current_app
from app.models import Partida, Evento, Temporada
from app.schemas import PartidaSchema
from app import cache
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select
from app.database.async_db import get_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

matches_bp = Blueprint('matches', __name__)
match_schema = PartidaSchema()
matches_schema = PartidaSchema(many=True)

@matches_bp.route('/', methods=['GET'])
@cache.cached(timeout=1800, query_string=True)  # 30 minutos, varia por query params
async def get_matches():
    try:
        rodada = request.args.get('rodada', type=int)
        time_id = request.args.get('time_id', type=int)
        
        # Input validation
        if rodada is not None and (rodada < 1 or rodada > 38):
            return jsonify({"error": "Invalid rodada: must be between 1 and 38"}), 400
        if time_id is not None and time_id < 1:
            return jsonify({"error": "Invalid time_id: must be positive"}), 400
        
        # Configurar sessão async
        engine = get_async_engine()
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        async with async_session() as session:
            # Construir query com style 2.0 (select)
            # Carregando relacionamentos necessários para evitar MissingGreenlet no Marshmallow
            stmt = select(Partida).options(
                joinedload(Partida.time_casa),
                joinedload(Partida.time_fora),
                joinedload(Partida.estadio),
                joinedload(Partida.arbitro),
                joinedload(Partida.estatisticas),
                selectinload(Partida.eventos).joinedload(Evento.time),
                selectinload(Partida.eventos).joinedload(Evento.jogador),
                joinedload(Partida.temporada)
            )
            
            if rodada:
                stmt = stmt.filter_by(rodada=rodada)
            if time_id:
                stmt = stmt.filter((Partida.time_casa_id == time_id) | (Partida.time_fora_id == time_id))
                
            stmt = stmt.order_by(Partida.rodada.desc(), Partida.data_hora.desc())
            
            # Executar query async
            result = await session.execute(stmt)
            partidas = result.scalars().all()
            
            current_app.logger.info(f"Fetched {len(partidas)} matches - ASYNC")
            return jsonify(matches_schema.dump(partidas))
            
    except Exception as e:
        current_app.logger.error(f"Error fetching matches: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch matches"}), 500

@matches_bp.route('/<int:match_id>', methods=['GET'])
@cache.cached(timeout=3600)  # 1 hora
async def get_match(match_id):
    from werkzeug.exceptions import NotFound
    try:
        # Input validation
        if match_id < 1:
            return jsonify({"error": "Invalid match_id: must be positive"}), 400
            
        # Configurar sessão async
        engine = get_async_engine()
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            # Query otimizada com eager loading completo
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
                current_app.logger.warning(f"Match not found: ID={match_id}")
                return jsonify({"error": "Resource not found", "status": 404}), 404

            current_app.logger.info(f"Fetched match details: ID={match_id} - ASYNC")
            return jsonify(match_schema.dump(partida))

    except NotFound:
        raise
    except Exception as e:
        current_app.logger.error(f"Error fetching match {match_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch match"}), 500
