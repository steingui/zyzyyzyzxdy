from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
from datetime import datetime

from app.config import Config

# Extensões globais
db = SQLAlchemy()
ma = Marshmallow()
migrate = Migrate()
cache = Cache()

# Configurar logging estruturado (RFC 005 - TOON)
from app.utils.logger import ToonFormatter

def setup_logging(app):
    # Remove default handlers to avoid duplication
    del app.logger.handlers[:]
    
    handler = logging.StreamHandler()
    formatter = ToonFormatter()
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar cache (agora usa as configurações do config.py)
    # app.config['CACHE_TYPE'] = 'SimpleCache' -> Removido em favor da configuração via Config object
    
    # Security: CORS Configuration
    # Adjust 'origins' for production to whitelist only your domains
    CORS(app, resources={
        r"/api/*": {
            "origins": os.getenv('CORS_ORIGINS', '*').split(','),  # Use '*' for dev, specific domains for prod
            "methods": ["GET", "OPTIONS"],  # Read-only API
            "allow_headers": ["Content-Type", "Accept"]
        }
    })
    
    # Security: Rate Limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

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
    from app.routes.scrape import scrape_bp

    app.register_blueprint(matches_bp, url_prefix='/api/matches')
    app.register_blueprint(teams_bp, url_prefix='/api/teams')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(scrape_bp)  # Já tem url_prefix='/api/scrape' no blueprint

    # V2 Blueprints
    from app.blueprints.v2.matches import matches_v2_bp
    app.register_blueprint(matches_v2_bp, url_prefix='/api/v2/matches')

    # Code-First Swagger (V2)
    from app.swagger import swagger_bp as swagger_v2_bp
    app.register_blueprint(swagger_v2_bp)
    
    # Swagger UI (Code-First)
    from app.routes.swagger_ui import swagger_ui
    app.add_url_rule('/api/docs', 'swagger_ui', swagger_ui)
    
    # Legacy Swagger/OpenAPI files removed
    # Redirects handled by new UI serving from /api/docs

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

    @app.route('/')
    def index():
        return jsonify({
            "name": "BR-Statistics Hub API",
            "version": "6.0.0",
            "documentation": "/api/docs",
            "status": "ready"
        }), 200

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'version': '6.0.0'}, 200
    
    # Security: HTTP Security Headers
    @app.after_request
    def set_security_headers(response):
        from flask import request
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Only add HSTS if using HTTPS
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    return app
