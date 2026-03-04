from flask import Blueprint, current_app, jsonify

bp = Blueprint("catalog", __name__)


@bp.get("/catalog")
def catalog():
    """
    Public SPA endpoint exposing Harbor's catalog of services.
    """
    services = current_app.registry.all_services()

    data = []
    for s in services:
        # Include only things meant to appear in the SPA
        if getattr(s, "public", True):
            data.append(
                {
                    "id": s.id,
                    "prefix": s.prefix,
                    "type": s.kind,
                    "upstreams": getattr(s, "upstreams", None),
                    "directory": getattr(s, "directory", None),
                    "source": s.source,
                }
            )

    return jsonify(data)
