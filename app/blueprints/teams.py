from flask import Blueprint, jsonify, current_app
from app.models import Time
from app.schemas import TimeSchema
from app import cache

teams_bp = Blueprint('teams', __name__)
time_schema = TimeSchema()
teams_schema = TimeSchema(many=True)

@teams_bp.route('/', methods=['GET'])
@cache.cached(timeout=3600)  # 1 hora - lista de times muda raramente
def get_teams():
    try:
        times = Time.query.order_by(Time.nome).all()
        current_app.logger.info(f"Fetched {len(times)} teams")
        return jsonify(teams_schema.dump(times))
    except Exception as e:
        current_app.logger.error(f"Error fetching teams: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch teams"}), 500

@teams_bp.route('/<int:team_id>', methods=['GET'])
@cache.cached(timeout=3600)  # 1 hora
def get_team(team_id):
    from werkzeug.exceptions import NotFound
    try:
        time = Time.query.get_or_404(team_id)
        current_app.logger.info(f"Fetched team: ID={team_id}")
        return jsonify(time_schema.dump(time))
    except NotFound:
        current_app.logger.warning(f"Team not found: ID={team_id}")
        raise  # Re-raise para Flask tratar
    except Exception as e:
        current_app.logger.error(f"Error fetching team {team_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch team"}), 500
