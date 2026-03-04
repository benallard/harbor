import requests

from flask import request, Response, send_from_directory, abort

from .base import ProxyBackend
from .router import Router


class FlaskProxyBackend(ProxyBackend):

    def __init__(self, app):

        self.app = app
        self.router = Router()

        self._install_gateway()

    def apply(self, services):

        self.router.rebuild(services)

    def _install_gateway(self):

        @self.app.route("/", defaults={"path": ""}, methods=[
            "GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"
        ])
        @self.app.route("/<path:path>", methods=[
            "GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"
        ])
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

        resp = requests.request(
            method=request.method,
            url=url,
            headers=self._filtered_headers(),
            data=request.get_data(),
            cookies=request.cookies,
            stream=True,
            allow_redirects=False
        )

        excluded = [
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection"
        ]

        headers = [
            (k, v) for k, v in resp.raw.headers.items()
            if k.lower() not in excluded
        ]

        return Response(
            resp.content,
            resp.status_code,
            headers
        )

    def _filtered_headers(self):

        excluded = ["host", "content-length"]

        return {
            k: v for k, v in request.headers
            if k.lower() not in excluded
        }