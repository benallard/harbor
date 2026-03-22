import logging

from ..core.config import BackendConfig
from .base import ProxyBackend
from .caddy import CaddyBackend
from .envoy import EnvoyBackend
from .flask_proxy import FlaskProxyBackend

logger = logging.getLogger(__name__)


def create_backend(app, name: str, config: BackendConfig) -> ProxyBackend:
    logger.info("Creating backend %s (%s) at %s", name, config.kind, config.url)

    if config.kind == "caddy":
        server_name = config.options.get("server-name", "srv0")
        return CaddyBackend(config.url, server_name=server_name)

    if config.kind == "envoy":
        return EnvoyBackend(config)

    if config.kind == "flask":
        return FlaskProxyBackend(app)

    raise RuntimeError(f"Unsupported backend: {config.kind}")
