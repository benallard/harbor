from harbor.proxy.router import Router
from harbor.core.models import Service


def test_router_prefix_match():

    router = Router()

    services = [
        Service(id="grafana", prefix="/grafana", kind="proxy"),
        Service(id="api", prefix="/grafana/api", kind="proxy"),
    ]

    router.rebuild(services)

    service, sub = router.match("/grafana/api/users")

    assert service.id == "api"
    assert sub == "users"


def test_router_root_match():

    router = Router()

    services = [
        Service(id="root", prefix="/", kind="proxy")
    ]

    router.rebuild(services)

    service, sub = router.match("/test")

    assert service.id == "root"
    assert sub == "test"