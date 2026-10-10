import pytest
import json
import re
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


ROUTES_URL = "http://localhost:2019/config/apps/http/servers/srv0/routes"
CATCH_ALL = {"handle": [{"handler": "file_server"}], "terminal": True}


@pytest.fixture
def backend():
    return CaddyBackend(BackendConfig(kind="caddy", url="http://localhost:2019"))


def test_register_new_proxy_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    requests = httpx_mock.get_requests()
    assert [r.method for r in requests] == ["GET", "GET", "PUT"]

    body = json.loads(requests[-1].content)
    assert body["@id"] == "ephemeral-svc1"
    assert body["match"][0]["path"] == ["/test*"]
    assert body["handle"][0]["handler"] == "rewrite"
    assert body["handle"][1]["handler"] == "reverse_proxy"


def test_register_existing_proxy_service(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET",
        url="http://localhost:2019/id/ephemeral-svc1",
        json={"@id": "ephemeral-svc1", "match": [{"path": ["/test*"]}]},
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
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    requests = httpx_mock.get_requests()
    body = json.loads(requests[-1].content)
    assert body["handle"][1]["handler"] == "file_server"
    assert body["handle"][1]["root"] == "/srv/test"


def test_register_static_service_without_spa_has_no_fallback(
    backend, httpx_mock: HTTPXMock
):
    service = make_service("svc1", kind="static")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert [h["handler"] for h in body["handle"]] == ["rewrite", "file_server"]


def test_register_static_service_spa(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1", kind="static")
    service.spa = True

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert [h["handler"] for h in body["handle"]] == [
        "rewrite",
        "subroute",
        "file_server",
    ]
    fallback, cache = body["handle"][1]["routes"]
    assert fallback["match"] == [
        {
            "not": [
                {
                    "file": {
                        "root": "/srv/test",
                        "try_files": [
                            "{http.request.uri.path}",
                            "{http.request.uri.path}/index.html",
                        ],
                    }
                },
                {"path_regexp": {"pattern": r"\.[^/]*$"}},
            ]
        }
    ]
    assert fallback["handle"] == [{"handler": "rewrite", "uri": "/index.html"}]
    assert cache["match"] == [{"path": ["/", "/index.html"]}]
    assert cache["handle"][0]["response"]["set"] == {"Cache-Control": ["no-cache"]}


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

    for service in services:
        httpx_mock.add_response(
            method="GET",
            url=f"http://localhost:2019/id/ephemeral-{service.id}",
            status_code=404,
        )
        httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
        httpx_mock.add_response(method="PUT", url=f"{ROUTES_URL}/0")
        backend.register(service)

    requests = httpx_mock.get_requests()
    assert len(requests) == 6  # GET route + GET routes + PUT for each service
    puts = [r for r in requests if r.method == "PUT"]
    assert len(puts) == 2


def test_on_event_registered(backend, httpx_mock: HTTPXMock):
    service = make_service("svc1")

    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.on_event("registered", service)

    requests = httpx_mock.get_requests()
    assert requests[-1].method == "PUT"


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
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[-1].content)
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
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[-1].content)
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
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=[CATCH_ALL])
    httpx_mock.add_response(
        method="PUT",
        url=f"{ROUTES_URL}/0",
        status_code=200,
    )

    backend.register(service)

    body = json.loads(httpx_mock.get_requests()[-1].content)
    # only one handler — reverse_proxy, no rewrite
    assert len(body["handle"]) == 1
    assert body["handle"][0]["handler"] == "reverse_proxy"
    assert body["handle"][0]["transport"]["versions"] == ["h2c"]


def _harbor_route(route_id, prefix):
    return {"@id": route_id, "match": [{"path": [f"{prefix}*"]}]}


def _register_into(backend, httpx_mock, service, routes):
    httpx_mock.add_response(
        method="GET",
        url=f"http://localhost:2019/id/ephemeral-{service.id}",
        status_code=404,
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, json=routes)
    httpx_mock.add_response(method="PUT", url=re.compile(rf"{ROUTES_URL}/\d+"))
    httpx_mock.add_response(method="POST", url=ROUTES_URL)
    backend.register(service)
    return httpx_mock.get_requests()[-1]


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_register_less_specific_route_goes_after_more_specific(
    backend, httpx_mock: HTTPXMock
):
    routes = [_harbor_route("static-api", "/app/api"), CATCH_ALL]
    request = _register_into(
        backend, httpx_mock, make_service("front", kind="static", prefix="/app"), routes
    )
    assert request.method == "PUT"
    assert request.url == f"{ROUTES_URL}/1"


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_register_more_specific_route_goes_before_less_specific(
    backend, httpx_mock: HTTPXMock
):
    routes = [_harbor_route("static-front", "/app"), CATCH_ALL]
    request = _register_into(
        backend, httpx_mock, make_service("api", prefix="/app/api"), routes
    )
    assert request.method == "PUT"
    assert request.url == f"{ROUTES_URL}/0"


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
def test_register_least_specific_route_is_appended_without_other_routes(
    backend, httpx_mock: HTTPXMock
):
    routes = [_harbor_route("static-api", "/app/api")]
    request = _register_into(
        backend, httpx_mock, make_service("front", kind="static", prefix="/app"), routes
    )
    assert request.method == "POST"
    assert request.url == ROUTES_URL


def test_register_existing_route_with_changed_prefix_is_moved(
    backend, httpx_mock: HTTPXMock
):
    service = make_service("svc1", prefix="/app/api")

    httpx_mock.add_response(
        method="GET",
        url="http://localhost:2019/id/ephemeral-svc1",
        json=_harbor_route("ephemeral-svc1", "/app"),
    )
    httpx_mock.add_response(
        method="DELETE", url="http://localhost:2019/id/ephemeral-svc1"
    )
    httpx_mock.add_response(
        method="GET",
        url=ROUTES_URL,
        json=[_harbor_route("static-front", "/app"), CATCH_ALL],
    )
    httpx_mock.add_response(method="PUT", url=f"{ROUTES_URL}/0")

    backend.register(service)

    assert [r.method for r in httpx_mock.get_requests()] == [
        "GET",
        "DELETE",
        "GET",
        "PUT",
    ]


def test_register_creates_routes_list_when_server_has_none(
    backend, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        method="GET", url="http://localhost:2019/id/ephemeral-svc1", status_code=404
    )
    httpx_mock.add_response(method="GET", url=ROUTES_URL, content=b"null")
    httpx_mock.add_response(method="PUT", url=ROUTES_URL)

    backend.register(make_service("svc1"))

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert [route["@id"] for route in body] == ["ephemeral-svc1"]
