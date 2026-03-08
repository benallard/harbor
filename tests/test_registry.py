import time
import pytest
from harbor.core.registry import Registry
from harbor.core.models import Service


def make_service(id, prefix="/test", kind="proxy"):
    return Service(
        id=id,
        prefix=prefix,
        kind=kind,
        upstreams=["127.0.0.1:5000"] if kind == "proxy" else None,
        directory="/tmp/test" if kind == "static" else None,
        source="dynamic",
    )


@pytest.fixture
def registry():
    return Registry(static_services={})


def test_register_dynamic(registry):
    service = make_service("svc1")
    lease = registry.register_dynamic(service, ttl=10)

    assert lease.service_id == "svc1"
    assert lease.ttl == 10
    assert "svc1" in registry.dynamic


def test_register_emits_event(registry):
    events = []
    registry.subscribe(lambda event, svc: events.append((event, svc.id)))

    service = make_service("svc1")
    registry.register_dynamic(service, ttl=10)

    assert events == [("registered", "svc1")]


def test_remove_dynamic(registry):
    service = make_service("svc1")
    registry.register_dynamic(service, ttl=10)
    result = registry.remove_dynamic("svc1")

    assert result is True
    assert "svc1" not in registry.dynamic


def test_remove_dynamic_emits_event(registry):
    events = []
    registry.subscribe(lambda event, svc: events.append((event, svc.id)))

    service = make_service("svc1")
    registry.register_dynamic(service, ttl=10)
    events.clear()  # ignore the registered event
    registry.remove_dynamic("svc1")

    assert events == [("unregistered", "svc1")]


def test_remove_dynamic_not_found(registry):
    result = registry.remove_dynamic("nonexistent")
    assert result is False


def test_renew_lease(registry):
    service = make_service("svc1")
    lease = registry.register_dynamic(service, ttl=10)
    old_expiry = lease.expires_at

    time.sleep(0.1)
    result = registry.renew("svc1", lease.token)

    assert result is True
    assert registry.leases["svc1"].expires_at > old_expiry


def test_renew_wrong_token(registry):
    service = make_service("svc1")
    registry.register_dynamic(service, ttl=10)
    result = registry.renew("svc1", "wrong-token")
    assert result is False


def test_renew_nonexistent(registry):
    result = registry.renew("nonexistent", "any-token")
    assert result is False


def test_remove_expired(registry):
    events = []
    registry.subscribe(lambda event, svc: events.append((event, svc.id)))

    service = make_service("svc1")
    registry.register_dynamic(service, ttl=1)
    events.clear()

    time.sleep(1.1)
    expired = registry.remove_expired()

    assert len(expired) == 1
    assert expired[0].id == "svc1"
    assert "svc1" not in registry.dynamic
    assert events == [("expired", "svc1")]


def test_remove_expired_keeps_valid(registry):
    svc1 = make_service("svc1")
    svc2 = make_service("svc2")
    registry.register_dynamic(svc1, ttl=1)
    registry.register_dynamic(svc2, ttl=60)

    time.sleep(1.1)
    expired = registry.remove_expired()

    assert len(expired) == 1
    assert expired[0].id == "svc1"
    assert "svc2" in registry.dynamic


def test_all_services_includes_static_and_dynamic():
    static = {"static-svc": make_service("static-svc", kind="static")}
    registry = Registry(static_services=static)
    registry.register_dynamic(make_service("dynamic-svc"), ttl=10)

    all_services = registry.all_services()
    ids = [s.id for s in all_services]

    assert "static-svc" in ids
    assert "dynamic-svc" in ids
