from unittest.mock import MagicMock
from harbor.core.dispatcher import Dispatcher
from harbor.core.config import HarborConfig, BackendConfig
from harbor.core.models import Service, Transcoder


def make_config(envoy_features=None):
    return HarborConfig(
        ingress="caddy",
        backends={
            "caddy": BackendConfig(
                kind="caddy",
                url="http://localhost:2019",
            ),
            "envoy": BackendConfig(
                kind="envoy",
                url="",
                options={"listener-port": "10000"},
                features=envoy_features or [],
            ),
        },
    )


def make_backends():
    caddy = MagicMock()
    caddy.listener_url = "127.0.0.1:80"
    envoy = MagicMock()
    envoy.listener_url = "127.0.0.1:10000"
    return {"caddy": caddy, "envoy": envoy}


def make_service(kind="proxy", sidecars=None, abilities=None):
    return Service(
        id="svc1",
        prefix="/svc1" if kind != "sidecar" else "",
        kind=kind,
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        sidecars=sidecars,
        abilities=abilities,
    )


def make_sidecar(abilities=None):
    return Service(
        id="my-bff",
        kind="sidecar",
        upstreams=["127.0.0.1:9091"],
        abilities=abilities or ["authz"],
        source="file",
    )


def make_dispatcher(config, backends, sidecars_for=None):
    registry = MagicMock()
    registry.get_sidecars_for = lambda s: sidecars_for or []
    return Dispatcher(config, backends, registry)


# --- apply ---


def test_apply_no_sidecars():
    config = make_config()
    backends = make_backends()
    dispatcher = make_dispatcher(config, backends)

    services = [make_service()]
    dispatcher.apply(services)

    backends["caddy"].on_event.assert_called_once_with("registered", services[0])
    backends["envoy"].on_event.assert_not_called()


def test_apply_with_authz_sidecar():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    dispatcher.apply([sidecar])  # sidecar itself should be registered with envoy
    backends["envoy"].on_event.assert_called_once_with("registered", sidecar)
    backends["caddy"].on_event.assert_not_called()

    backends["envoy"].reset_mock()

    services = [make_service(sidecars=["my-bff"])]
    dispatcher.apply(services)

    backends["caddy"].on_event.assert_called_once()
    backends["envoy"].on_event.assert_called_once()


def test_apply_with_transcoder_sidecar():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    services = [make_service(sidecars=["my-bff"])]
    dispatcher.apply(services)

    backends["caddy"].on_event.assert_called_once()
    backends["envoy"].on_event.assert_called_once()


# --- dispatch ---


def test_dispatch_no_sidecars():
    config = make_config()
    backends = make_backends()
    dispatcher = make_dispatcher(config, backends)

    service = make_service()
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()


def test_dispatch_with_authz_sidecar():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("registered", service)

    caddy_call = backends["caddy"].on_event.call_args
    assert caddy_call[0][0] == "registered"
    transformed = caddy_call[0][1]
    assert transformed.kind == "proxy"
    assert transformed.upstreams == ["127.0.0.1:10000"]
    assert transformed.id == service.id

    backends["envoy"].on_event.assert_called_once_with("registered", service)


def test_dispatch_with_transcoder_sidecar():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("registered", service)

    caddy_call = backends["caddy"].on_event.call_args
    transformed = caddy_call[0][1]
    assert transformed.upstreams == ["127.0.0.1:10000"]

    backends["envoy"].on_event.assert_called_once_with("registered", service)


def test_dispatch_transform_preserves_original():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("registered", service)

    assert service.kind == "proxy"
    assert service.upstreams == ["127.0.0.1:9090"]
    assert service.sidecars == ["my-bff"]


def test_dispatch_unregister_with_sidecar():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("unregistered", service)

    backends["caddy"].on_event.assert_called_once()
    backends["envoy"].on_event.assert_called_once_with("unregistered", service)


def test_dispatch_no_sidecars_goes_to_ingress_only():
    config = make_config(envoy_features=["authz", "transcoder"])
    backends = make_backends()
    dispatcher = make_dispatcher(config, backends)

    service = make_service()
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()


# --- sidecar dispatch ---


def test_dispatch_sidecar_to_capable_backend():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    dispatcher = make_dispatcher(config, backends)

    sidecar = make_sidecar(abilities=["authz"])
    dispatcher.dispatch("registered", sidecar)

    backends["envoy"].on_event.assert_called_once_with("registered", sidecar)
    backends["caddy"].on_event.assert_not_called()


def test_dispatch_sidecar_no_capable_backend():
    config = make_config(envoy_features=[])
    backends = make_backends()
    dispatcher = make_dispatcher(config, backends)

    sidecar = make_sidecar(abilities=["authz"])
    dispatcher.dispatch("registered", sidecar)

    backends["caddy"].on_event.assert_not_called()
    backends["envoy"].on_event.assert_not_called()


# --- transform and multi-route dispatch ---


def test_dispatch_transcoder_generates_rest_route(httpx_mock):
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = Service(
        id="svc1",
        prefix="/api/myservice",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        sidecars=["my-transcoder"],
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        ),
        protocol="http2",
    )

    dispatcher.dispatch("registered", service)

    # caddy should receive at least the REST route
    caddy_calls = backends["caddy"].on_event.call_args_list
    rest_call = next(
        (c for c in caddy_calls if c[0][1].prefix == "/api/myservice"), None
    )
    assert rest_call is not None
    transformed = rest_call[0][1]
    assert transformed.strip_prefix is True
    assert transformed.upstreams == ["127.0.0.1:10000"]
    assert transformed.protocol == "http2"


def test_dispatch_transcoder_generates_grpc_passthrough_route():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = Service(
        id="svc1",
        prefix="/api/myservice",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        sidecars=["my-transcoder"],
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        ),
        protocol="http2",
    )

    dispatcher.dispatch("registered", service)

    caddy_calls = backends["caddy"].on_event.call_args_list
    grpc_call = next(
        (c for c in caddy_calls if c[0][1].prefix == "/myservice.v1.MyService"), None
    )
    assert grpc_call is not None
    transformed = grpc_call[0][1]
    assert transformed.strip_prefix is False
    assert transformed.upstreams == ["127.0.0.1:10000"]
    assert transformed.protocol == "http2"
    # Transcoder left unchanged, ingress should not care
    assert transformed.transcoder.services[0] == "myservice.v1.MyService"


def test_dispatch_transcoder_envoy_receives_original():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = Service(
        id="svc1",
        prefix="/api/myservice",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        sidecars=["my-transcoder"],
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService"],
        ),
        protocol="http2",
    )

    dispatcher.dispatch("registered", service)

    envoy_call = backends["envoy"].on_event.call_args
    assert envoy_call[0][0] == "registered"
    assert envoy_call[0][1] is service  # original, untouched


def test_dispatch_unregister_removes_all_ingress_routes():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = Service(
        id="svc1",
        prefix="/api/myservice",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        sidecars=["my-transcoder"],
        transcoder=Transcoder(
            proto_descriptor="/etc/harbor/proto/svc.pb",
            services=["myservice.v1.MyService", "myservice.v1.AnotherService"],
        ),
        protocol="http2",
    )

    # register first to populate _ingress_ids
    dispatcher.dispatch("registered", service)
    backends["caddy"].on_event.reset_mock()
    backends["envoy"].on_event.reset_mock()

    # now unregister
    dispatcher.dispatch("unregistered", service)

    caddy_calls = backends["caddy"].on_event.call_args_list
    removed_ids = [c[0][1].id for c in caddy_calls]

    # both the REST and gRPC routes should be removed
    assert "svc1" in removed_ids
    assert any("grpc" in id for id in removed_ids)

    # envoy also notified
    backends["envoy"].on_event.assert_called_once_with("unregistered", service)


def test_dispatch_no_transcoder_single_ingress_route():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("registered", service)

    # only one caddy call — no gRPC passthrough when no transcoder
    assert backends["caddy"].on_event.call_count == 1


def test_dispatch_unregister_no_transcoder_removes_single_route():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    service = make_service(sidecars=["my-bff"])
    dispatcher.dispatch("registered", service)
    backends["caddy"].on_event.reset_mock()

    dispatcher.dispatch("unregistered", service)

    assert backends["caddy"].on_event.call_count == 1
    removed = backends["caddy"].on_event.call_args[0][1]
    assert removed.id == service.id
