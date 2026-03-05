from flask import Blueprint, request, jsonify, current_app
from harbor.core.models import Service

bp = Blueprint("services", __name__)


@bp.get("/services")
def list_services():
    """
    Returns all registered services (static + dynamic) for the SPA.
    """
    services = current_app.registry.all_services()

    data = []
    for s in services:
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


@bp.post("/services")
def create_service():
    """
    Registers a new dynamic service with optional TTL.
    """
    data = request.json
    if not data or "id" not in data or "prefix" not in data or "type" not in data:
        return jsonify({"error": "missing required fields"}), 400
    service = Service.from_dict(data, "dynamic")
    ttl = data.get("ttl", 60)
    lease = current_app.registry.register_dynamic(service, ttl=ttl)

    # Rebuild proxy routes
    current_app.reload_proxy()

    return jsonify({"id": service.id, "lease": lease.token, "ttl": lease.ttl}), 201


@bp.delete("/services/<id>")
def delete_service(id):
    """
    Deletes a dynamic service.
    """
    removed = current_app.registry.remove_dynamic(id)

    if not removed:
        return jsonify({"error": "service not found"}), 404

    # Rebuild proxy routes
    current_app.reload_proxy()

    return jsonify({"status": "deleted"}), 200


@bp.post("/service/<id>/renew")
def renew(id):
    """
    Renews the TTL for a dynamic service using its lease token.
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "missing Authorization header"}), 401

    success = current_app.registry.renew(id, token)
    if not success:
        return jsonify({"error": "invalid lease"}), 403

    return jsonify({"status": "renewed"}), 200
