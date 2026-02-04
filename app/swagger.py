from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from flask import Blueprint, jsonify

# Create APISpec
spec = APISpec(
    title="BR-Statistics Hub API",
    version="v2.0.0",
    openapi_version="3.0.2",
    info=dict(
        description="API for Brazilian Football Statistics - Brasileirão. V2 introduces standardized response envelopes and enhanced pagination."
    ),
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
)

# Reference definitions for common responses (Standard Envelope)
# This will be used in docstrings to avoid repetition
spec.components.schema("PaginationMeta", {
    "type": "object",
    "properties": {
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "per_page": {"type": "integer"},
        "pages": {"type": "integer"}
    }
})

spec.components.schema("Meta", {
    "type": "object",
    "properties": {
        "pagination": {"$ref": "#/components/schemas/PaginationMeta"},
        "version": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"}
    }
})

spec.components.schema("Links", {
    "type": "object",
    "properties": {
        "self": {"type": "string"},
        "next": {"type": "string", "nullable": True},
        "prev": {"type": "string", "nullable": True}
    }
})

swagger_bp = Blueprint('swagger', __name__)

@swagger_bp.route('/api/docs/spec.json')
def spec_json():
    """
    Serve the generated OpenAPI spec
    """
    # 1. Register Schemas from our app
    # We do this lazily or here to avoid circular imports during startup
    from app.blueprints.v2.schemas import PartidaSchema, TimeSchema
    
    # Check if schemas are already registered to prevent DuplicateComponentNameError
    if "Partida" not in spec.components.schemas:
        spec.components.schema("Partida", schema=PartidaSchema)
    if "Time" not in spec.components.schemas:
        spec.components.schema("Time", schema=TimeSchema)
    
    # 2. Parse paths from view functions
    # New V2 Views
    from flask import current_app
    from app.blueprints.v2.matches import get_matches, get_match
    
    # We use the current_app context to inspect view functions
    with current_app.test_request_context():
        spec.path(view=get_matches, app=current_app)
        spec.path(view=get_match, app=current_app)

    return jsonify(spec.to_dict())
