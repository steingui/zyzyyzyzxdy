from flask import Blueprint, jsonify, request, current_app
from app.models import Partida
from app.schemas import PartidaSchema
from app import cache
from sqlalchemy.orm import joinedload, selectinload

matches_bp = Blueprint('matches', __name__)
match_schema = PartidaSchema()
matches_schema = PartidaSchema(many=True)

@matches_bp.route('/', methods=['GET'])
@cache.cached(timeout=1800, query_string=True)  # 30 minutos, varia por query params
def get_matches():
    try:
        rodada = request.args.get('rodada', type=int)
        time_id = request.args.get('time_id', type=int)
        
        # Input validation
        if rodada is not None and (rodada < 1 or rodada > 38):
            return jsonify({"error": "Invalid rodada: must be between 1 and 38"}), 400
        if time_id is not None and time_id < 1:
            return jsonify({"error": "Invalid time_id: must be positive"}), 400
        
        # Otimização: Eager Loading para evitar N+1 queries
        query = Partida.query.options(
            joinedload(Partida.time_casa),
            joinedload(Partida.time_fora),
            joinedload(Partida.estadio),
            joinedload(Partida.arbitro),
            joinedload(Partida.estatisticas),
            # selectinload é mais eficiente para conexões One-to-Many grandes
            selectinload(Partida.eventos)
        )
        
        if rodada:
            query = query.filter_by(rodada=rodada)
        if time_id:
            query = query.filter((Partida.time_casa_id == time_id) | (Partida.time_fora_id == time_id))
            
        partidas = query.order_by(Partida.rodada.desc(), Partida.data_hora.desc()).all()
        current_app.logger.info(f"Fetched {len(partidas)} matches (rodada={rodada}, time_id={time_id})")
        return jsonify(matches_schema.dump(partidas))
    except Exception as e:
        current_app.logger.error(f"Error fetching matches: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch matches"}), 500

@matches_bp.route('/<int:match_id>', methods=['GET'])
@cache.cached(timeout=3600)  # 1 hora para partidas específicas
def get_match(match_id):
    from werkzeug.exceptions import NotFound
    try:
        # Input validation
        if match_id < 1:
            return jsonify({"error": "Invalid match_id: must be positive"}), 400
            
        # Otimização: Eager Loading
        partida = Partida.query.options(
            joinedload(Partida.time_casa),
            joinedload(Partida.time_fora),
            joinedload(Partida.estadio),
            joinedload(Partida.arbitro),
            joinedload(Partida.estatisticas),
            selectinload(Partida.eventos)
        ).filter_by(id=match_id).first_or_404()
        
        current_app.logger.info(f"Fetched match details: ID={match_id}")
        return jsonify(match_schema.dump(partida))
    except NotFound:
        current_app.logger.warning(f"Match not found: ID={match_id}")
        raise  # Re-raise para deixar Flask tratar o 404
    except Exception as e:
        current_app.logger.error(f"Error fetching match {match_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch match"}), 500
