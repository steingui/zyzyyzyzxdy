from flask import Blueprint, jsonify, current_app
from app import db, cache
import sqlalchemy

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/ranking-xg', methods=['GET'])
@cache.cached(timeout=1800)  # 30 minutos - muda só a cada rodada
def get_ranking_xg():
    try:
        # Usando a View que criamos no RDS (004_analysis_views.sql)
        query = sqlalchemy.text("SELECT * FROM v_ranking_xg")
        result = db.session.execute(query)
        
        ranking = []
        for row in result:
            ranking.append({
                "team": row.time,
                "matches": row.jogos,
                "avg_xg_for": float(row.xg_favor_medio),
                "avg_xg_against": float(row.xg_contra_medio)
            })
            
        current_app.logger.info(f"Ranking xG retrieved: {len(ranking)} teams")
        return jsonify(ranking)
    except Exception as e:
        current_app.logger.error(f"Error fetching ranking xG: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch ranking data"}), 500

@analytics_bp.route('/summary', methods=['GET'])
@cache.cached(timeout=1800)  # 30 minutos - estatísticas gerais
def get_overall_summary():
    try:
        # Exemplo de agregação rápida via SQL
        query = sqlalchemy.text("""
            SELECT 
                COUNT(*) as total_jogos,
                SUM(gols_casa + gols_fora) as total_gols
            FROM partidas 
            WHERE status = 'finished'
        """)
        result = db.session.execute(query).fetchone()
        
        summary = {
            "total_matches": result.total_jogos,
            "total_goals": result.total_gols,
            "avg_goals": round(result.total_gols / result.total_jogos, 2) if result.total_jogos > 0 else 0
        }
        
        current_app.logger.info(f"Summary retrieved: {summary}")
        return jsonify(summary)
    except Exception as e:
        current_app.logger.error(f"Error fetching summary: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch summary data"}), 500
