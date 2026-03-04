from flask import Blueprint, request

from ..core.models import Service
from ..core import registry

bp = Blueprint("services", __name__)


@bp.post("/services")
def create_service():

    data = request.json

    service = Service(
        id=data["id"],
        prefix=data["prefix"],
        kind=data["type"],
        upstreams=data.get("upstreams"),
        source="dynamic",
    )

    lease = registry.register_dynamic(service, data.get("ttl", 60))

    reload_proxy()

    return {"id": service.id, "lease": lease.token, "ttl": lease.ttl}


@bp.post("/service/<id>/renew")
def renew(id):

    token = request.headers.get("Authorization")

    if not registry.renew(id, token):
        return {"error": "invalid lease"}, 403

    return {"status": "renewed"}
