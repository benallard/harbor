from flask import Blueprint, request, jsonify
from ..core.models import Service
from ..core.registry import Registry

bp = Blueprint("services", __name__)

_registry: Registry = None


def create_bp(registry: Registry):
    global _registry, _backend
    _registry = registry
    return bp


@bp.get("/services")
def list_services():
    services = _registry.all_services()
    return jsonify(
        [
            {
                "id": s.id,
                "prefix": s.prefix,
                "type": s.kind,
                "upstreams": s.upstreams,
                "directory": s.directory,
                "source": s.source,
            }
            for s in services
        ]
    )


@bp.post("/services")
def create_service():
    data = request.json
    if not data or "id" not in data or "prefix" not in data or "type" not in data:
        return jsonify({"error": "missing required fields"}), 400
    service = Service.from_dict(data, "dynamic")
    ttl = data.get("ttl", 60)
    lease = _registry.register_dynamic(service, ttl)
    return jsonify({"id": service.id, "lease": lease.token, "ttl": lease.ttl}), 201


@bp.delete("/services/<id>")
def delete_service(id):
    service = _registry.dynamic.get(id)
    if not service:
        return jsonify({"error": "service not found"}), 404
    _registry.remove_dynamic(id)
    return jsonify({"status": "deleted"}), 200


@bp.post("/services/<id>/renew")
def renew(id):
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "missing Authorization header"}), 401
    if not _registry.renew(id, token):
        return jsonify({"error": "invalid lease"}), 403
    return jsonify({"status": "renewed"}), 200
