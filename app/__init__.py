from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_caching import Cache
from flask_swagger_ui import get_swaggerui_blueprint
import os
import logging
import json
from datetime import datetime

from app.config import Config

# Extensões globais
db = SQLAlchemy()
ma = Marshmallow()
migrate = Migrate()
cache = Cache()

# Configurar logging estruturado
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def setup_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar cache local
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutos

    # Inicializar extensões com o app
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    setup_logging(app)

    # Registrar Blueprints
    from app.blueprints.matches import matches_bp
    from app.blueprints.teams import teams_bp
    from app.blueprints.analytics import analytics_bp

    app.register_blueprint(matches_bp, url_prefix='/api/matches')
    app.register_blueprint(teams_bp, url_prefix='/api/teams')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    # Swagger UI - English
    SWAGGER_URL_EN = '/api/docs/en'
    API_URL_EN = '/openapi-en.yaml'
    swaggerui_bp_en = get_swaggerui_blueprint(
        SWAGGER_URL_EN,
        API_URL_EN,
        config={'app_name': "BR-Statistics Hub API (EN)"}
    )
    app.register_blueprint(swaggerui_bp_en, url_prefix=SWAGGER_URL_EN)
    
    # Swagger UI - Portuguese
    SWAGGER_URL_PT = '/api/docs/pt'
    API_URL_PT = '/openapi-pt.yaml'
    swaggerui_bp_pt = get_swaggerui_blueprint(
        SWAGGER_URL_PT,
        API_URL_PT,
        config={'app_name': "BR-Statistics Hub API (PT-BR)"}
    )
    app.register_blueprint(swaggerui_bp_pt, url_prefix=SWAGGER_URL_PT)
    
    # Servir os arquivos OpenAPI
    @app.route('/openapi-en.yaml')
    def openapi_spec_en():
        from flask import send_from_directory
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return send_from_directory(project_root, 'openapi-en.yaml')
    
    @app.route('/openapi-pt.yaml')
    def openapi_spec_pt():
        from flask import send_from_directory
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return send_from_directory(project_root, 'openapi-pt.yaml')
    
    # Redirect /api/docs to English by default
    @app.route('/api/docs')
    def redirect_to_docs():
        from flask import redirect
        return redirect('/api/docs/en')

    # Error Handlers
    @app.errorhandler(404)
    def not_found(error):
        app.logger.warning(f"404 Not Found: {error}")
        return jsonify({"error": "Resource not found", "status": 404}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Internal Server Error: {error}", exc_info=True)
        return jsonify({"error": "Internal server error", "status": 500}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f"Unhandled exception: {error}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "status": 500}), 500

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'version': '2.0.0'}, 200

    return app
