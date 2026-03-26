import logging
from typing import Optional

from .config import HarborConfig
from .models import Service

logger = logging.getLogger(__name__)


class Dispatcher:

    def __init__(self, config: HarborConfig, backends: dict):
        self.config = config
        self.backends = backends

    def apply(self, services):
        ingress = self.backends[self.config.ingress]
        ingress.apply(services)

        for service in services:
            delegate_name = self._find_delegate(service)
            if delegate_name:
                self.backends[delegate_name].apply([service])

    def _find_delegate(self, service: Service) -> Optional[str]:
        service_features = set()
        if service.transcoder:
            service_features.add("transcoder")
        if service.bff:
            service_features.add("bff")

        if not service_features:
            return None

        for name, config in self.config.backends.items():
            if name == self.config.ingress:
                continue
            if any(f in config.features for f in service_features):
                return name
        return None

    def dispatch(self, event: str, service: Service):
        ingress_backend = self.backends[self.config.ingress]
        delegate_name = self._find_delegate(service)

        if delegate_name:
            delegate_backend = self.backends[delegate_name]
            transformed = self._transform(service, delegate_backend)
            logger.debug(
                "Dispatching %s to ingress %s as proxy → %s",
                service.id,
                self.config.ingress,
                delegate_name,
            )
            ingress_backend.on_event(event, transformed)
            logger.debug("Dispatching %s to delegate %s", service.id, delegate_name)
            delegate_backend.on_event(event, service)
        else:
            ingress_backend.on_event(event, service)

    def _transform(self, service: Service, delegate_backend) -> Service:
        from dataclasses import replace

        return replace(
            service,
            kind="proxy",
            upstreams=[delegate_backend.listener_url],
        )
