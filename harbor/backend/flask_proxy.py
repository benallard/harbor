import httpx

from flask import request, Response, send_from_directory, abort

from .base import ProxyBackend


class FlaskProxyBackend(ProxyBackend):

    def __init__(self, app):
        self.app = app
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

        excluded_req = {"host", "content-length"}
        headers = {k: v for k, v in request.headers if k.lower() not in excluded_req}

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
