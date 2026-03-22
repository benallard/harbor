import logging
from .config import HarborConfig
from .models import Service
from ..proxy.base import ProxyBackend

logger = logging.getLogger(__name__)


class Dispatcher:

    def __init__(self, config: HarborConfig, backends: dict):
        self.config = config
        self.backends = backends

    def apply(self, services):
        ingress = self.backends[self.config.ingress]
        ingress.apply(services)

        # apply delegated services to their respective backends
        ingress_config = self.config.backends[self.config.ingress]
        for service in services:
            delegate_name = ingress_config.delegate.get(service.kind)
            if delegate_name:
                self.backends[delegate_name].apply([service])

    def dispatch(self, event: str, service: Service):
        ingress_name = self.config.ingress
        ingress_config = self.config.backends[ingress_name]
        ingress_backend = self.backends[ingress_name]

        delegate_name = ingress_config.delegate.get(service.kind)

        if delegate_name:
            # transform service for ingress — proxy to delegate's listener
            delegate_backend = self.backends[delegate_name]
            transformed = self._transform(service, delegate_backend)
            logger.debug(
                "Dispatching %s to ingress %s as proxy → %s",
                service.id, ingress_name, delegate_name
            )
            ingress_backend.on_event(event, transformed)

            # dispatch original service to delegate
            logger.debug(
                "Dispatching %s to delegate %s",
                service.id, delegate_name
            )
            self.backends[delegate_name].on_event(event, service)

        else:
            # no delegation — ingress handles it directly
            ingress_backend.on_event(event, service)

    def _transform(self, service: Service, delegate_backend) -> Service:
        from dataclasses import replace
        return replace(
            service,
            kind="proxy",
            upstreams=[delegate_backend.listener_url],
        )