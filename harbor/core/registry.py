import secrets
import time
from .models import Service, Lease


class Registry:

    def __init__(self, static_services):
        self.static = static_services
        self.dynamic = {}
        self.leases = {}

    def register_dynamic(self, service: Service, ttl: int):

        token = secrets.token_hex(16)

        lease = Lease(
            service_id=service.id, token=token, ttl=ttl, expires_at=time.time() + ttl
        )

        self.dynamic[service.id] = service
        self.leases[service.id] = lease

        return lease

    def renew(self, service_id, token):

        lease = self.leases.get(service_id)

        if not lease:
            return False

        if lease.token != token:
            return False

        lease.expires_at = time.time() + lease.ttl
        return True

    def remove_expired(self):

        now = time.time()

        expired = [sid for sid, lease in self.leases.items() if lease.expires_at < now]

        for sid in expired:
            self.dynamic.pop(sid, None)
            self.leases.pop(sid, None)

        return expired

    def all_services(self):
        return list(self.static.values()) + list(self.dynamic.values())
