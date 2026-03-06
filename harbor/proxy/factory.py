from harbor.proxy.caddy import CaddyBackend
from harbor.proxy.flask_proxy import FlaskProxyBackend


def create_backend(app, backend, caddy_admin):

    if backend == "flask":
        return FlaskProxyBackend(app)

    if backend == "caddy":
        return CaddyBackend(caddy_admin)

    raise RuntimeError(f"Unsupported backend: {backend}")
