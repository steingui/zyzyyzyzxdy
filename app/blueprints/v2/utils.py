from flask import jsonify, request, url_for
from datetime import datetime

class ApiResponse:
    @staticmethod
    def success(data=None, meta=None, links=None, status_code=200):
        """
        Standard success response envelope.
        """
        response = {
            "data": data,
            "meta": meta or {},
            "links": links or {}
        }
        
        # Add timestamp and version to meta if not present
        if "timestamp" not in response["meta"]:
            response["meta"]["timestamp"] = datetime.utcnow().isoformat() + "Z"
        if "version" not in response["meta"]:
            response["meta"]["version"] = "v2.0.0"
            
        return jsonify(response), status_code

    @staticmethod
    def error(message, code="INTERNAL_ERROR", details=None, status_code=500):
        """
        Standard error response envelope (RFC 7807 inspired).
        """
        response = {
            "error": {
                "code": code,
                "message": message,
                "details": details or []
            },
            "status": status_code
        }
        return jsonify(response), status_code

    @staticmethod
    def paginate(pagination_obj, schema, endpoint, **kwargs):
        """
        Helper to create a paginated response.
        :param pagination_obj: SQLAlchemy Pagination object OR AsyncPagination object
        :param schema: Marshmallow schema for serializing items
        :param endpoint: Endpoint name for generating links
        :param kwargs: Additional query parameters to preserve in links
        """
        # Handle both standard Flask-SQLAlchemy Pagination and our custom AsyncPagination
        items = pagination_obj.items
        if hasattr(items, 'items'): # Double check if it's nested
             items = items.items

        data = schema.dump(items)
        
        meta = {
            "pagination": {
                "total": pagination_obj.total,
                "page": pagination_obj.page,
                "per_page": pagination_obj.per_page,
                "pages": pagination_obj.pages
            }
        }
        
        links = {}
        if pagination_obj.has_prev:
            links['prev'] = url_for(endpoint, page=pagination_obj.prev_num, **kwargs)
        else:
            links['prev'] = None
            
        if pagination_obj.has_next:
            links['next'] = url_for(endpoint, page=pagination_obj.next_num, **kwargs)
        else:
            links['next'] = None
            
        links['self'] = url_for(endpoint, page=pagination_obj.page, **kwargs)
        
        return ApiResponse.success(data=data, meta=meta, links=links)

class AsyncPagination:
    """
    Helper class to mimic Flask-SQLAlchemy Pagination for Async results
    """
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        
    @property
    def pages(self):
        if self.per_page == 0:
            return 0
        from math import ceil
        return ceil(self.total / self.per_page)
        
    @property
    def has_prev(self):
        return self.page > 1
        
    @property
    def has_next(self):
        return self.page < self.pages
        
    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None
        
    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None
