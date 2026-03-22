from dataclasses import dataclass
import httpx

from flask import request, Response, send_from_directory, abort

from .base import ProxyBackend
from ..core.config import BackendConfig


@dataclass
class FlaskConfig:
    listener_port: int = 8080

    @staticmethod
    def from_backend_config(config: BackendConfig) -> "FlaskConfig":
        return FlaskConfig(
            listener_port=int(config.options.get("listener-port", 8080)),
        )


class FlaskProxyBackend(ProxyBackend):

    def __init__(self, app, config: BackendConfig):
        self.app = app
        self.config = FlaskConfig.from_backend_config(config)
        self.router = Router()
        self.client = httpx.Client()
        self._install_gateway()

    def apply(self, services):
        self.router.rebuild(services)

    def register(self, service):
        self.router.add(service)

    def unregister(self, service):
        self.router.remove(service)

    def on_event(self, event, service):
        if event == "registered":
            self.register(service)
        elif event in ("unregistered", "expired"):
            self.unregister(service)

    def _install_gateway(self):

        @self.app.route(
            "/",
            defaults={"path": ""},
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        )
        @self.app.route(
            "/<path:path>",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        )
        def gateway(path):
            full_path = "/" + path
            service, subpath = self.router.match(full_path)

            if not service:
                abort(404)

            if service.kind == "proxy":
                return self._proxy(service, subpath)

            if service.kind == "static":
                return self._serve_static(service, subpath)

            abort(500)

    def _serve_static(self, service, subpath):
        if not service.directory:
            abort(500)
        return send_from_directory(service.directory, subpath)

    def _proxy(self, service, subpath):
        upstream = service.upstreams[0]
        url = upstream.rstrip("/") + "/" + subpath

        headers = self._filtered_headers()
        headers.update(
            {
                "X-Forwarded-For": request.remote_addr,
                "X-Forwarded-Proto": request.scheme,
                "X-Forwarded-Prefix": service.prefix,
                "X-Real-IP": request.remote_addr,
                "Host": request.host,
                "Forwarded": f"for={request.remote_addr};host={request.host};proto={request.scheme}",
            }
        )

        resp = self.client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=request.get_data(),
            cookies=dict(request.cookies),
            follow_redirects=False,
        )

        excluded_resp = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        }
        headers = [
            (k, v) for k, v in resp.headers.items() if k.lower() not in excluded_resp
        ]

        return Response(resp.content, resp.status_code, headers)

    def _filtered_headers(self):
        excluded = {"host", "content-length"}
        return {k: v for k, v in request.headers if k.lower() not in excluded}

    @property
    def listener_url(self) -> str:
        return f"127.0.0.1:{self.config.listener_port}"


class Router:

    def __init__(self):
        self.routes = []

    def rebuild(self, services):
        # longest prefix first
        self.routes = sorted(services, key=lambda s: len(s.prefix), reverse=True)

    def add(self, service):
        self.routes.append(service)
        self.routes.sort(key=lambda s: len(s.prefix), reverse=True)

    def remove(self, service):
        self.routes = [r for r in self.routes if r.id != service.id]

    def match(self, path):
        for service in self.routes:
            prefix = service.prefix.rstrip("/")

            if path == prefix:
                return service, ""

            if path.startswith(prefix + "/"):
                subpath = path[len(prefix) + 1 :]
                return service, subpath

        return None, None
