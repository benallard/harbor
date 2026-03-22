import logging
import os
import json
import tempfile
from pathlib import Path
from .base import ProxyBackend
from ..core.models import Service
from ..core.config import BackendConfig

logger = logging.getLogger(__name__)

ENVOY_RUN_DIR = Path("/run/envoy")
CDS_PATH = ENVOY_RUN_DIR / "cds.yaml"
LDS_PATH = ENVOY_RUN_DIR / "lds.yaml"


class EnvoyBackend(ProxyBackend):

    def __init__(self, config: BackendConfig):
        self.config = config
        self.clusters = {}   # service_id → cluster config
        self.routes = {}     # service_id → route config
        ENVOY_RUN_DIR.mkdir(parents=True, exist_ok=True)

    def apply(self, services):
        for service in services:
            self._add(service)
        self._write()

    def register(self, service: Service):
        self._add(service)
        self._write()

    def unregister(self, service: Service):
        self.clusters.pop(service.id, None)
        self.routes.pop(service.id, None)
        self._write()

    def on_event(self, event: str, service: Service):
        if event == "registered":
            self.register(service)
        elif event in ("unregistered", "expired"):
            self.unregister(service)

    def _add(self, service: Service):
        self.clusters[service.id] = render_cluster(service)
        self.routes[service.id] = render_route(service)

    def _write(self):
        _atomic_write(CDS_PATH, {"resources": list(self.clusters.values())})
        _atomic_write(LDS_PATH, {"resources": list(self.routes.values())})


def _atomic_write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.rename(tmp, path)


def render_cluster(service: Service) -> dict:
    pass


def render_route(service: Service) -> dict:
    pass