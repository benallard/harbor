import logging
from typing import List, Optional, Tuple
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

    def _find_backends_covering(self, features: set) -> List[str]:
        """Return list of backend names that support all of the given features."""
        return [
            name
            for name, config in self.config.backends.items()
            if features <= set(config.features)
        ]

    def _service_features(self, service: Service) -> set:
        """Return set of features required by the service, based on its sidecars."""
        sidecars = self.registry.get_sidecars_for(service)
        return {a for s in sidecars for a in (s.abilities or [])}

    def _find_delegate(self, service: Service) -> Tuple[Optional[str], Optional[str]]:
        """
        Return the backend the service is delegated to, or why it cannot be routed.
        A service that cannot get all the features its sidecars stand for must not be routed without them.
        """
        known = {s.id for s in self.registry.get_sidecars_for(service)}
        missing = [sid for sid in service.sidecars or [] if sid not in known]
        if missing:
            return None, f"sidecars {missing} are not registered"
        features = self._service_features(service)
        if not features:
            return None, None
        backends = self._find_backends_covering(features)
        if not backends:
            return None, f"no backend supports all of the features {sorted(features)}"
        if len(backends) > 1:
            logger.warning(
                "Multiple backends %s support features %s required by service %s, using %s",
                backends,
                features,
                service.id,
                backends[0],
            )
        return backends[0], None

    def _dependents_of(self, sidecar: Service) -> List[Service]:
        return [
            s for s in self.registry.all_services() if sidecar.id in (s.sidecars or [])
        ]

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
            # The services using this sidecar are routed or withdrawn depending on whether it exists.
            for dependent in self._dependents_of(service):
                self.dispatch("registered", dependent)
            return

        ingress_backend = self.backends[self.config.ingress]
        delegate_name, problem = self._find_delegate(service)

        if problem:
            if event == "registered":
                logger.error("Service %s is not routed: %s", service.id, problem)
            # Withdraw what the backends may still route for it from before.
            for route in _transform(service, service.upstreams):
                ingress_backend.on_event("unregistered", route)
            for name, backend in self.backends.items():
                if name != self.config.ingress:
                    backend.on_event("unregistered", service)
        elif delegate_name:
            # Tell the ingress how to reach the service
            for transformed in _transform(
                service, [self.backends[delegate_name].listener_url]
            ):
                ingress_backend.on_event(event, transformed)
            # And tell the proper backend to apply it.
            self.backends[delegate_name].on_event(event, service)
        else:
            ingress_backend.on_event(event, service)


def _transform(service: Service, upstreams: List[str]) -> List[Service]:
    """
    Transform the service into a (set of) proxy that the ingress can route to the delegate backend at `upstreams`.
    """
    routes = [
        replace(
            service,
            kind="proxy",
            upstreams=upstreams,
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
                    upstreams=upstreams,
                    strip_prefix=False,
                    protocol="http2",  # Those must be grpc
                )
            )
    return routes
