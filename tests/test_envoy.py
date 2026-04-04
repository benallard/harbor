import json
import pytest
from unittest.mock import patch
from harbor.backend.envoy import (
    EnvoyBackend,
    render_cluster,
    render_route,
    render_sidecar_cluster,
)
from harbor.core.config import BackendConfig
from harbor.core.models import Service, Transcoder


def make_service(
    id="svc1",
    prefix="/api/myservice",
    kind="proxy",
    protocol=None,
    transcoder=None,
    sidecars=None,
    strip_prefix=True,
):
    return Service(
        id=id,
        prefix=prefix,
        kind=kind,
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        protocol=protocol,
        transcoder=transcoder,
        sidecars=sidecars,
        strip_prefix=strip_prefix,
    )


def make_sidecar(id="my-bff", abilities=None):
    return Service(
        id=id,
        kind="sidecar",
        abilities=abilities or ["authz"],
        upstreams=["127.0.0.1:9091"],
        source="file",
    )


@pytest.fixture
def backend(tmp_path):
    config = BackendConfig(
        kind="envoy",
        url=str(tmp_path),  # run directory, not an HTTP URL
        options={"listener-port": "10000"},
    )
    return EnvoyBackend(config)


# --- render_cluster ---


def test_render_cluster_basic():
    service = make_service()
    cluster = render_cluster(service)
    assert cluster["name"] == "svc1"
    assert cluster["type"] == "STRICT_DNS"
    assert "typed_extension_protocol_options" not in cluster


def test_render_cluster_http2():
    service = make_service(protocol="http2")
    cluster = render_cluster(service)
    assert "typed_extension_protocol_options" in cluster
    opts = cluster["typed_extension_protocol_options"]
    proto = opts["envoy.extensions.upstreams.http.v3.HttpProtocolOptions"]
    assert "http2_protocol_options" in proto["explicit_http_config"]


def test_render_cluster_upstream_address():
    service = make_service()
    cluster = render_cluster(service)
    endpoint = cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]
    socket = endpoint["endpoint"]["address"]["socket_address"]
    assert socket["address"] == "127.0.0.1"
    assert socket["port_value"] == 9090


# --- render_route ---


def test_render_route_basic():
    service = make_service()
    route = render_route(service)
    assert route["match"]["prefix"] == "/api/myservice"
    assert route["route"]["cluster"] == "svc1"
    assert route["route"]["prefix_rewrite"] == "/"
    assert "typed_per_filter_config" not in route


def test_render_route_strips_prefix_with_transcoder():
    service = make_service(
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        )
    )
    route = render_route(service)
    assert route["route"]["prefix_rewrite"] == "/"


def test_render_route_transcoder_filter_config():
    service = make_service(
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        )
    )
    route = render_route(service)
    assert "typed_per_filter_config" in route
    transcoder_config = route["typed_per_filter_config"][
        "envoy.filters.http.grpc_json_transcoder"
    ]
    assert transcoder_config["proto_descriptor"] == "/etc/harbor/proto/svc.pb"
    assert "myservice.v1.MyService" in transcoder_config["services"]


# --- render_sidecar_cluster ---


def test_render_sidecar_cluster():
    sidecar = make_sidecar()
    cluster = render_sidecar_cluster(sidecar)
    assert cluster["name"] == "my-bff"
    assert (
        "typed_extension_protocol_options" in cluster
    )  # sidecars always speak grpc/http2
    endpoint = cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]
    socket = endpoint["endpoint"]["address"]["socket_address"]
    assert socket["address"] == "127.0.0.1"
    assert socket["port_value"] == 9091


# --- backend ---


def test_backend_register_writes_files(backend, tmp_path):
    service = make_service()
    backend.register(service)
    assert (tmp_path / "cds.yaml").exists()
    assert (tmp_path / "lds.yaml").exists()


def test_backend_register_adds_cluster(backend, tmp_path):
    service = make_service()
    backend.register(service)
    cds = json.loads((tmp_path / "cds.yaml").read_text())
    ids = [r["name"] for r in cds["resources"]]
    assert "svc1" in ids


def test_backend_register_adds_route(backend, tmp_path):
    service = make_service()
    backend.register(service)
    lds = json.loads((tmp_path / "lds.yaml").read_text())
    routes = lds["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"][
        "route_config"
    ]["virtual_hosts"][0]["routes"]
    prefixes = [r["match"]["prefix"] for r in routes]
    assert "/api/myservice" in prefixes


def test_backend_unregister_removes_cluster(backend, tmp_path):
    service = make_service()
    backend.register(service)
    backend.unregister(service)
    cds = json.loads((tmp_path / "cds.yaml").read_text())
    ids = [r["name"] for r in cds["resources"]]
    assert "svc1" not in ids


def test_backend_unregister_removes_route(backend, tmp_path):
    service = make_service()
    backend.register(service)
    backend.unregister(service)
    lds = json.loads((tmp_path / "lds.yaml").read_text())
    routes = lds["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"][
        "route_config"
    ]["virtual_hosts"][0]["routes"]
    prefixes = [r["match"]["prefix"] for r in routes]
    assert "/api/myservice" not in prefixes


def test_backend_sidecar_adds_cluster_not_route(backend, tmp_path):
    sidecar = make_sidecar()
    backend.on_event("registered", sidecar)
    cds = json.loads((tmp_path / "cds.yaml").read_text())
    lds = json.loads((tmp_path / "lds.yaml").read_text())
    cluster_ids = [r["name"] for r in cds["resources"]]
    routes = lds["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"][
        "route_config"
    ]["virtual_hosts"][0]["routes"]
    assert "my-bff" in cluster_ids
    assert not any(r["route"]["cluster"] == "my-bff" for r in routes)


def test_backend_authz_sidecar_wires_ext_authz_filter(backend, tmp_path):
    sidecar = make_sidecar(abilities=["authz"])
    backend.on_event("registered", sidecar)
    lds = json.loads((tmp_path / "lds.yaml").read_text())
    filters = lds["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"][
        "http_filters"
    ]
    filter_names = [f["name"] for f in filters]
    assert "envoy.filters.http.ext_authz" in filter_names
    authz = next(f for f in filters if f["name"] == "envoy.filters.http.ext_authz")
    assert (
        authz["typed_config"]["grpc_service"]["envoy_grpc"]["cluster_name"] == "my-bff"
    )


def test_backend_unregister_authz_sidecar_removes_filter(backend, tmp_path):
    sidecar = make_sidecar(abilities=["authz"])
    backend.on_event("registered", sidecar)
    backend.on_event("unregistered", sidecar)
    lds = json.loads((tmp_path / "lds.yaml").read_text())
    filters = lds["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"][
        "http_filters"
    ]
    filter_names = [f["name"] for f in filters]
    assert "envoy.filters.http.ext_authz" not in filter_names


def test_backend_listener_url(backend):
    assert backend.listener_url == "localhost:10000"


def test_backend_apply(backend, tmp_path):
    services = [make_service("svc1"), make_service("svc2", prefix="/api/other")]
    for service in services:
        backend.register(service)
    cds = json.loads((tmp_path / "cds.yaml").read_text())
    ids = [r["name"] for r in cds["resources"]]
    assert "svc1" in ids
    assert "svc2" in ids


# --- Explicit transcoder tests ---


def test_envoy_render_route_transcoder_strips_prefix():
    service = Service(
        id="svc1",
        prefix="/api/myservice",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        protocol="http2",
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        ),
    )

    route = render_route(service)

    # when transcoder is present, prefix must be stripped
    assert route["route"]["prefix_rewrite"] == "/"
    # match should be on the full prefix
    assert route["match"]["prefix"] == "/api/myservice"
