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


@bp.get("/catalog/icon/<service_id>")
def catalog_icon(service_id: str):
    """
    Endpoint to retrieve the icon for a given service.
    Returns the icon URL or base64 string, or 404 if not found.
    """
    services = current_app.registry.all_services()
    service = next((s for s in services if s.id == service_id), None)
    if service and getattr(service, "icon", None):
        return jsonify({"icon": service.icon})
    # Optionally, return a default icon or 404
    return jsonify({"icon": None}), 404
