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
        for service in services:
            self.dispatch("registered", service)

    def _find_backends_for(self, features: set) -> List[str]:
        """Return list of backend names that support any of the given features."""
        return [
            name
            for name, config in self.config.backends.items()
            if any(f in config.features for f in features)
        ]

    def _service_features(self, service: Service) -> set:
        """Return set of features required by the service, based on its sidecars."""
        sidecars = self.registry.get_sidecars_for(service)
        return {a for s in sidecars for a in (s.abilities or [])}

    def _find_delegate(self, service: Service) -> Optional[str]:
        features = self._service_features(service)
        if not features:
            return None
        backends = self._find_backends_for(features)
        if backends and len(backends) > 1:
            logger.warning(
                "Multiple backends %s support features %s required by service %s, using %s",
                backends,
                features,
                service.id,
                backends[0],
            )
        return backends[0] if backends else None

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
            # Tell the ingress how to reach the service
            for transformed in _transform(service, self.backends[delegate_name]):
                ingress_backend.on_event(event, transformed)
            # And tell the proper backend to apply it.
            self.backends[delegate_name].on_event(event, service)
        else:
            ingress_backend.on_event(event, service)


def _transform(service: Service, delegate_backend) -> List[Service]:
    """
    Transform the service into a (set of) proxy that the ingress can route to the delegate backend.
    """
    routes = [
        replace(
            service,
            kind="proxy",
            upstreams=[delegate_backend.listener_url],
            strip_prefix=service.transcoder
            is not None,  # When we have a transcoder, we should strip the prefix for the REST part
        )
    ]

    if service.transcoder:
        # Ironically, this is triggered by the transcoder, but is not the transcoded part itself.
        for grpc_service in service.transcoder.services:
            # Tell the ingress to let pass requests to the gRPC service,
            # without stripping the prefix (as gRPC services are identified by it)
            routes.append(
                replace(
                    service,
                    id=f"{service.id}-grpc-{grpc_service.replace('.', '-')}",
                    kind="proxy",
                    prefix=f"/{grpc_service}",
                    upstreams=[delegate_backend.listener_url],
                    strip_prefix=False,
                    protocol="http2",  # Those must be grpc
                )
            )
    return routes
