import secrets
import time
from typing import Dict, List, Optional

from .models import Service, Lease


class Registry:
    def __init__(self, static_services: Dict[str, Service]) -> None:
        self.static: Dict[str, Service] = static_services
        self.dynamic: Dict[str, Service] = {}
        self.leases: Dict[str, Lease] = {}

    def register_dynamic(self, service: Service, ttl: int) -> Lease:
        token: str = secrets.token_hex(16)
        lease: Lease = Lease(
            service_id=service.id, token=token, ttl=ttl, expires_at=time.time() + ttl
        )
        self.dynamic[service.id] = service
        self.leases[service.id] = lease
        return lease

    def renew(self, service_id: str, token: str) -> bool:
        lease: Optional[Lease] = self.leases.get(service_id)
        if not lease:
            return False
        if lease.token != token:
            return False
        lease.expires_at = time.time() + lease.ttl
        return True

    def remove_expired(self) -> List[str]:
        now: float = time.time()
        expired: List[str] = [
            sid for sid, lease in self.leases.items() if lease.expires_at < now
        ]
        for sid in expired:
            self.dynamic.pop(sid, None)
            self.leases.pop(sid, None)
        return expired

    def all_services(self) -> List[Service]:
        return list(self.static.values()) + list(self.dynamic.values())
