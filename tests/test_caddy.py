import pytest
import json
from pytest_httpx import HTTPXMock
from harbor.backend.caddy import CaddyBackend
from harbor.core.models import Service
from harbor.core.config import BackendConfig


def make_service(id, kind="proxy", prefix="/test"):
    return Service(
        id=id,
        prefix=prefix,
        kind=kind,
        upstreams=["127.0.0.1:5000"] if kind == "proxy" else None,
        directory="/srv/test" if kind == "static" else None,
        source="dynamic",
    )


@pytest.fixture
def backend():
    return CaddyBackend(BackendConfig(kind="caddy", url="http://localhost:2019"))


def test_register_new_proxy_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.register(service)

    requests = httpx_mock.get_requests()
    assert requests[0].method == "GET"
    assert requests[1].method == "PUT"

    body = json.loads(requests[1].content)
    assert body["@id"] == "ephemeral-svc1"
    assert body["match"][0]["path"] == ["/test*"]
    assert body["handle"][0]["handler"] == "rewrite"
    assert body["handle"][1]["handler"] == "reverse_proxy"


def test_register_existing_proxy_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=200
    )
    httpx_mock.add_response(
        method="PATCH", url="http://localhost:2019/id/ephemeral-svc1", status_code=200
    )

    backend.register(service)

    requests = httpx_mock.get_requests()
    assert requests[0].method == "GET"
    assert requests[1].method == "PATCH"


def test_register_static_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1", kind="static")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.register(service)

    requests = httpx_mock.get_requests()
    body = json.loads(requests[1].content)
    assert body["handle"][1]["handler"] == "file_server"
    assert body["handle"][1]["root"] == "/srv/test"


def test_unregister_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="DELETE", url="http://localhost:2019/id/ephemeral-svc1", status_code=200
    )

    backend.unregister(service)

    requests = httpx_mock.get_requests()
    assert requests[0].method == "DELETE"
    assert "/id/ephemeral-svc1" in str(requests[0].url)


def test_apply_static_services(backend, httpx_mock: HTTPXMock):
    services = [make_service("svc1"), make_service("svc2")]

    for _ in services:
        httpx_mock.add_response(method="GET", status_code=404)
        httpx_mock.add_response(method="PUT", status_code=200)

    backend.apply(services)

    requests = httpx_mock.get_requests()
    assert len(requests) == 4  # GET + PUT for each service
    posts = [r for r in requests if r.method == "PUT"]
    assert len(posts) == 2


def test_on_event_registered(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.on_event("registered", service)

    requests = httpx_mock.get_requests()
    assert requests[1].method == "PUT"


def test_on_event_unregistered(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="DELETE", url="http://localhost:2019/id/ephemeral-svc1", status_code=200
    )

    backend.on_event("unregistered", service)

    requests = httpx_mock.get_requests()
    assert requests[0].method == "DELETE"


def test_on_event_expired(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="DELETE", url="http://localhost:2019/id/ephemeral-svc1", status_code=200
    )

    backend.on_event("expired", service)

    requests = httpx_mock.get_requests()
    assert requests[0].method == "DELETE"


def test_on_event_unknown(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")
    # should not raise, just log a warning
    backend.on_event("unknown", service)
    assert len(httpx_mock.get_requests()) == 0


def test_register_proxy_service_no_strip_prefix(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")
    service = Service(
        id="svc1",
        prefix="/test",
        kind="proxy",
        upstreams=["127.0.0.1:5000"],
        source="dynamic",
        strip_prefix=False,
    )

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[1].content)
    # no rewrite handler when strip_prefix=False
    assert body["handle"][0]["handler"] == "reverse_proxy"


def test_register_proxy_service_http2(backend, httpx_mock: HTTPXMock):
    service = Service(
        id="svc1",
        prefix="/test",
        kind="proxy",
        upstreams=["127.0.0.1:5000"],
        source="dynamic",
        protocol="http2",
    )

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[1].content)
    proxy = body["handle"][1]
    assert proxy["handler"] == "reverse_proxy"
    assert proxy["transport"]["versions"] == ["h2c"]


def test_register_proxy_service_no_strip_prefix_no_rewrite(
    backend, httpx_mock: HTTPXMock
):
    service = Service(
        id="svc1",
        prefix="/test",
        kind="proxy",
        upstreams=["127.0.0.1:5000"],
        source="dynamic",
        strip_prefix=False,
        protocol="http2",
    )

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(
        method="PUT",
        url="http://localhost:2019/config/apps/http/servers/srv0/routes/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[1].content)
    # only one handler — reverse_proxy, no rewrite
    assert len(body["handle"]) == 1
    assert body["handle"][0]["handler"] == "reverse_proxy"
    assert body["handle"][0]["transport"]["versions"] == ["h2c"]
