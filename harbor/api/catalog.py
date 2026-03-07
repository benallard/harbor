from flask import Blueprint, jsonify, Response
import json
import queue
import threading
from ..core.registry import Registry
from ..core.models import Service

bp = Blueprint("catalog", __name__)

_registry: Registry = None
_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()


def create_bp(registry: Registry):
    global _registry
    _registry = registry
    return bp


def _serialize(service):
    return {
        "id": service.id,
        "name": service.name or service.id,
        "prefix": service.prefix,
        "icon": service.icon,
    }


def notify_subscribers(event: str, service: Service):
    payload = json.dumps({"event": event, "service": _serialize(service)})
    with _subscribers_lock:
        for q in _subscribers:
            q.put(payload)


@bp.get("/catalog")
def catalog():
    services = _registry.all_services()
    return jsonify([_serialize(s) for s in services if s.public])


@bp.get("/catalog/icon/<service_id>")
def catalog_icon(service_id: str):
    service = _registry.static.get(service_id) or _registry.dynamic.get(service_id)
    if service and service.icon:
        return jsonify({"icon": service.icon})
    return jsonify({"icon": None}), 404


@bp.get("/catalog/stream")
def catalog_stream():
    def stream():
        q = queue.Queue()
        with _subscribers_lock:
            _subscribers.append(q)
        try:
            while True:
                payload = q.get()
                yield f"data: {payload}\n\n"
        except GeneratorExit:
            with _subscribers_lock:
                _subscribers.remove(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
