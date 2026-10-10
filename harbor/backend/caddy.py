from dataclasses import dataclass

import httpx
import logging
import threading

from typing import Optional

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
        self.routes_path = f"/config/apps/http/servers/{self.config.server_name}/routes"
        self._lock = threading.Lock()

    def _upsert_route(self, route_id: str, route: dict):
        route["@id"] = route_id
        with self._lock:
            response = self.client.get(f"/id/{route_id}")
            if response.status_code != 404:
                if _specificity(response.json()) == _specificity(route):
                    logger.debug("Updating route %s for service %s", route_id, route)
                    self.client.patch(f"/id/{route_id}", json=route)
                    return
                logger.debug("Moving route %s, its prefix changed", route_id)
                self.client.delete(f"/id/{route_id}")
            self._insert_route(route_id, route)

    def _insert_route(self, route_id: str, route: dict):
        # Keep Harbor routes ordered most specific first, ahead of any other route (e.g. the catch-all).
        response = self.client.get(self.routes_path)
        routes = response.json() if response.status_code == 200 else None
        if routes is None:
            logger.debug("Creating routes list with route %s: %s", route_id, route)
            self.client.put(self.routes_path, json=[route])
            return
        specificity = _specificity(route)
        index = next(
            (
                i
                for i, existing in enumerate(routes)
                if not _is_harbor_route(existing)
                or _specificity(existing) <= specificity
            ),
            len(routes),
        )
        logger.debug("Creating new route %s at index %s: %s", route_id, index, route)
        if index < len(routes):
            self.client.put(f"{self.routes_path}/{index}", json=route)
        else:
            self.client.post(self.routes_path, json=route)

    def register(self, service: Service):
        logger.debug("Registering service %s with CaddyBackend", service.id)
        prefix = "static" if service.source == "file" else "ephemeral"
        route = render_route(service)
        if not route:
            logger.warning("No route rendered for service %s", service.id)
            return
        self._upsert_route(f"{prefix}-{service.id}", route)

    def unregister(self, service: Service):
        logger.debug("Unregistering service %s from CaddyBackend", service.id)
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


def _is_harbor_route(route: dict) -> bool:
    return route.get("@id", "").startswith(("static-", "ephemeral-"))


def _specificity(route: dict) -> int:
    """Length of the longest literal path prefix the route matches."""
    return max(
        (
            len(path.rstrip("*"))
            for matcher in route.get("match", [])
            for path in matcher.get("path", [])
        ),
        default=0,
    )


def render_route(service: Service) -> Optional[dict]:
    if service.kind == "proxy":
        return _render_proxy_route(service)
    elif service.kind == "static":
        return _render_static_route(service)
    return None


def _render_proxy_route(service: Service) -> dict:
    if service.public_paths:
        paths = [f"{service.prefix}{p}" for p in service.public_paths]
    else:
        paths = [f"{service.prefix}*"]

    handlers = []

    if service.strip_prefix:
        handlers.append({"handler": "rewrite", "strip_path_prefix": service.prefix})

    proxy = {
        "handler": "reverse_proxy",
        "upstreams": [{"dial": upstream} for upstream in (service.upstreams or [])],
        "headers": {
            "request": {
                "set": {
                    "X-Forwarded-For": ["{http.request.remote.host}"],
                    "X-Forwarded-Proto": ["{http.request.scheme}"],
                    "X-Forwarded-Prefix": [service.prefix],
                    "X-Real-IP": ["{http.request.remote.host}"],
                    "Host": ["{http.request.host}"],
                    "Forwarded": [
                        "for={http.request.remote.host};host={http.request.host};proto={http.request.scheme}"
                    ],
                }
            }
        },
    }

    if service.protocol == "http2":
        proxy["transport"] = {"protocol": "http", "versions": ["h2c"]}

    handlers.append(proxy)

    return {
        "match": [{"path": paths}],
        "handle": handlers,
    }


def _render_static_route(service: Service) -> dict:
    handlers = [{"handler": "rewrite", "strip_path_prefix": service.prefix}]
    if service.spa:
        handlers.append(_render_spa_fallback(service))
    handlers.append({"handler": "file_server", "root": service.directory})
    return {
        "match": [{"path": [f"{service.prefix}*"]}],
        "handle": handlers,
    }


def _render_spa_fallback(service: Service) -> dict:
    # Paths with a file extension are left alone, so a missing asset still returns 404.
    not_found_without_extension = {
        "not": [
            {
                "file": {
                    "root": service.directory,
                    "try_files": [
                        "{http.request.uri.path}",
                        "{http.request.uri.path}/index.html",
                    ],
                }
            },
            {"path_regexp": {"pattern": r"\.[^/]*$"}},
        ]
    }
    return {
        "handler": "subroute",
        "routes": [
            {
                "match": [not_found_without_extension],
                "handle": [{"handler": "rewrite", "uri": "/index.html"}],
            },
            {
                "match": [{"path": ["/", "/index.html"]}],
                "handle": [
                    {
                        "handler": "headers",
                        "response": {"set": {"Cache-Control": ["no-cache"]}},
                    }
                ],
            },
        ],
    }
