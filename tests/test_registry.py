import time

from harbor.core.registry import Registry
from harbor.core.models import Service


def test_register_dynamic_service():

    registry = Registry()

    service = Service(
        id="test",
        prefix="/test",
        kind="proxy",
        upstreams=["http://localhost:5000"],
        source="dynamic",
    )

    lease = registry.register_dynamic(service, ttl=10)

    assert lease.service_id == "test"
    assert "test" in registry.dynamic


def test_lease_expiry():

    registry = Registry()

    service = Service(
        id="expire",
        prefix="/expire",
        kind="proxy",
        upstreams=["http://x"],
        source="dynamic",
    )

    registry.register_dynamic(service, ttl=1)

    time.sleep(2)

    expired = registry.remove_expired()

    assert "expire" in expired