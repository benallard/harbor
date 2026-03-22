import logging

from ..core.config import BackendConfig
from .base import ProxyBackend
from .caddy import CaddyBackend
from .envoy import EnvoyBackend
from .flask_proxy import FlaskProxyBackend

logger = logging.getLogger(__name__)

BACKENDS = {
    "caddy": CaddyBackend,
    "envoy": EnvoyBackend,
    "flask": FlaskProxyBackend,
}


def create_backend(app, name: str, config: BackendConfig) -> ProxyBackend:
    logger.info("Creating backend %s (%s) at %s", name, config.kind, config.url)
    cls = BACKENDS.get(config.kind)
    if cls is None:
        raise RuntimeError(f"Unsupported backend: {config.kind}")
    if config.kind == "flask":
        return cls(app, config)
    return cls(config)