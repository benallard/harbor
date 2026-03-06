import httpx
import logging
from .base import ProxyBackend
from ..core.models import Service

logger = logging.getLogger(__name__)


class CaddyBackend(ProxyBackend):

    def __init__(self, admin_url: str):
        if admin_url.startswith("unix://"):
            socket_path = admin_url[len("unix://") :]
            transport = httpx.HTTPTransport(uds=socket_path)
            self.client = httpx.Client(transport=transport, base_url="http://caddy")
        else:
            self.client = httpx.Client(base_url=admin_url)

    def _upsert_route(self, route_id: str, route: dict):
        route["@id"] = route_id
        response = self.client.get(f"/id/{route_id}")
        if response.status_code == 404:
            self.client.put("/config/apps/http/servers/harbor/routes", json=route)
        else:
            self.client.patch(f"/id/{route_id}", json=route)

    def apply(self, services):
        for service in services:
            route = render_route(service)
            self._upsert_route(f"static-{service.id}", route)

    def register(self, service: Service):
        route = render_route(service)
        self._upsert_route(f"ephemeral-{service.id}", route)

    def unregister(self, service: Service):
        self.client.delete(f"/id/ephemeral-{service.id}")

    def on_event(self, event: str, service: Service):
        if event == "registered":
            self.register(service)
        elif event in ("unregistered", "expired"):
            self.unregister(service)
        else:
            logger.warning(
                "CaddyBackend: unknown event %s for service %s", event, service.id
            )


def render_route(service: Service):
    if service.kind == "proxy":
        # If public_paths is set, use it; otherwise, proxy everything under prefix
        paths = service.public_paths or [f"{service.prefix}*"]

        route = {
            "match": [{"path": paths}],
            "handle": [
                {
                    "handler": "reverse_proxy",
                    "upstreams": [
                        {"dial": upstream} for upstream in (service.upstreams or [])
                    ],
                }
            ],
        }
        return route
    elif service.kind == "static":
        route = {
            "match": [{"path": [f"{service.prefix}*"]}],
            "handle": [{"handler": "file_server", "root": service.directory}],
        }
        return route
