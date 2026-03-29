from dataclasses import dataclass

import httpx
import logging

from ..core.config import BackendConfig
from .base import ProxyBackend
from ..core.models import Service

logger = logging.getLogger(__name__)


@dataclass
class CaddyConfig:
    server_name: str = "srv0"
    listener_port: int = 80

    @staticmethod
    def from_backend_config(config: BackendConfig) -> "CaddyConfig":
        return CaddyConfig(
            server_name=config.options.get("server-name", "srv0"),
            listener_port=int(config.options.get("listener-port", 80)),
        )


class CaddyBackend(ProxyBackend):

    def __init__(self, config: BackendConfig):
        self.config = CaddyConfig.from_backend_config(config)
        admin_url = config.url

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
            logger.debug("Creating new route %s for service %s", route_id, route)
            self.client.put(
                f"/config/apps/http/servers/{self.config.server_name}/routes/0",
                json=route,
            )
        else:
            logger.debug("Updating route %s for service %s", route_id, route)
            self.client.patch(f"/id/{route_id}", json=route)

    def apply(self, services):
        for service in services:
            logger.info("Applying static service %s at %s", service.id, service.prefix)
            route = render_route(service)
            self._upsert_route(f"static-{service.id}", route)

    def register(self, service: Service):
        prefix = "static" if service.source == "file" else "ephemeral"
        route = render_route(service)
        self._upsert_route(f"{prefix}-{service.id}", route)

    def unregister(self, service: Service):
        prefix = "static" if service.source == "file" else "ephemeral"
        self.client.delete(f"/id/{prefix}-{service.id}")

    def on_event(self, event: str, service: Service):
        if event == "registered":
            self.register(service)
        elif event in ("unregistered", "expired"):
            self.unregister(service)
        else:
            logger.warning(
                "CaddyBackend: unknown event %s for service %s", event, service.id
            )

    @property
    def listener_url(self) -> str:
        return f"127.0.0.1:{self.config.listener_port}"


def render_route(service: Service) -> dict:
    if service.kind == "proxy":
       return _render_proxy_route(service)
    elif service.kind == "static":
        return _render_static_route(service)
    
def _render_proxy_route(service: Service) -> dict:
    if service.public_paths:
        paths = [f"{service.prefix}{p}" for p in service.public_paths]
    else:
        paths = [f"{service.prefix}*"]

    handlers = []

    if service.strip_prefix:
        handlers.append({
            "handler": "rewrite",
            "strip_path_prefix": service.prefix
        })

    proxy = {
        "handler": "reverse_proxy",
        "upstreams": [
            {"dial": upstream} for upstream in (service.upstreams or [])
        ],
        "headers": {
            "request": {
                "set": {
                    "X-Forwarded-For":    ["{http.request.remote.host}"],
                    "X-Forwarded-Proto":  ["{http.request.scheme}"],
                    "X-Forwarded-Prefix": [service.prefix],
                    "X-Real-IP":          ["{http.request.remote.host}"],
                    "Host":               ["{http.request.host}"],
                    "Forwarded":          ["for={http.request.remote.host};host={http.request.host};proto={http.request.scheme}"],
                }
            }
        },
    }

    if service.protocol == "http2":
        proxy["transport"] = {
            "protocol": "http",
            "versions": ["h2c"]
        }

    handlers.append(proxy)

    return {
        "match": [{"path": paths}],
        "handle": handlers,
    }

def _render_static_route(service: Service) -> dict:
    return {
        "match": [{"path": [f"{service.prefix}*"]}],
        "handle": [
            {"handler": "rewrite", "strip_path_prefix": service.prefix},
            {"handler": "file_server", "root": service.directory},
        ],
    }
