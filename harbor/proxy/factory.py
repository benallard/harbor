from harbor import config

from harbor.proxy.caddy import CaddyBackend
from harbor.proxy.flask_proxy import FlaskProxyBackend


def create_backend(app):

    if config.PROXY_BACKEND == "flask":
        return FlaskProxyBackend(app)

    if config.PROXY_BACKEND == "caddy":
        return CaddyBackend(config.CADDY_ADMIN)

    raise RuntimeError(f"Unsupported backend: {config.PROXY_BACKEND}")
