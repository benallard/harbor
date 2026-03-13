import secrets
import time
from typing import Dict, List, Optional, Callable

from .models import Service, Lease


class Registry:
    def __init__(self, static_services: Dict[str, Service]) -> None:
        self.static: Dict[str, Service] = static_services
        self.dynamic: Dict[str, Service] = {}
        self.leases: Dict[str, Lease] = {}
        self._listeners: List[Callable[[str, Service], None]] = []

    def subscribe(self, listener: Callable[[str, Service], None]):
        self._listeners.append(listener)

    def _emit(self, event: str, service: Service):
        for listener in self._listeners:
            listener(event, service)

    def add_static(self, service: Service) -> None:
        self.static[service.id] = service
        self._emit("registered", service)

    def remove_static(self, service_id: str) -> bool:
        service = self.static.pop(service_id, None)
        if service:
            self._emit("unregistered", service)
            return True
        return False

    def register_dynamic(self, service: Service, ttl: int) -> Lease:
        token: str = secrets.token_hex(16)
        lease: Lease = Lease(
            service_id=service.id, token=token, ttl=ttl, expires_at=time.time() + ttl
        )
        self.dynamic[service.id] = service
        self.leases[service.id] = lease
        self._emit("registered", service)
        return lease

    def remove_dynamic(self, service_id: str) -> bool:
        service = self.dynamic.pop(service_id, None)
        self.leases.pop(service_id, None)
        if service:
            self._emit("unregistered", service)
            return True
        return False

    def remove_expired(self) -> List[Service]:
        now: float = time.time()
        expired: List[Service] = [
            self.dynamic[sid]
            for sid, lease in self.leases.items()
            if lease.expires_at < now and sid in self.dynamic
        ]
        for service in expired:
            self.dynamic.pop(service.id, None)
            self.leases.pop(service.id, None)
            self._emit("expired", service)
        return expired

    def renew(self, service_id: str, token: str) -> bool:
        lease: Optional[Lease] = self.leases.get(service_id)
        if not lease:
            return False
        if lease.token != token:
            return False
        lease.expires_at = time.time() + lease.ttl
        return True

    def all_services(self) -> List[Service]:
        return list(self.static.values()) + list(self.dynamic.values())
