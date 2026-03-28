import logging
from typing import List, Optional
from dataclasses import replace

from .registry import Registry
from .config import HarborConfig
from .models import Service

logger = logging.getLogger(__name__)


class Dispatcher:

    def __init__(self, config: HarborConfig, backends: dict, registry: Registry):
        self.config = config
        self.backends = backends
        self.registry = registry

    def apply(self, services):
        ingress = self.backends[self.config.ingress]
        ingress.apply(services)

        for service in services:
            delegate_name = self._find_delegate(service)
            if delegate_name:
                self.backends[delegate_name].apply([service])

    def _find_backends_for(self, features: set) -> List[str]:
        return [
            name
            for name, config in self.config.backends.items()
            if any(f in config.features for f in features)
        ]

    def _service_features(self, service: Service) -> set:
        sidecars = self.registry.get_sidecars_for(service)
        return {a for s in sidecars for a in (s.abilities or [])}

    def _find_delegate(self, service: Service) -> Optional[str]:
        features = self._service_features(service)
        if not features:
            return None
        backends = self._find_backends_for(features)
        delegates = [b for b in backends if b != self.config.ingress]
        return delegates[0] if delegates else None

    def dispatch(self, event: str, service: Service):
        if service.kind == "sidecar":
            backends = self._find_backends_for(set(service.abilities or []))
            if not backends:
                logger.warning(
                    "Sidecar %s with abilities %s has no capable backend",
                    service.id,
                    service.abilities,
                )
            for name in backends:
                self.backends[name].on_event(event, service)
            return

        ingress_backend = self.backends[self.config.ingress]
        delegate_name = self._find_delegate(service)

        if delegate_name:
            transformed = _transform(service, self.backends[delegate_name])
            ingress_backend.on_event(event, transformed)
            self.backends[delegate_name].on_event(event, service)
        else:
            ingress_backend.on_event(event, service)


def _transform(service: Service, delegate_backend) -> Service:
    return replace(
        service,
        kind="proxy",
        upstreams=[delegate_backend.listener_url],
    )
