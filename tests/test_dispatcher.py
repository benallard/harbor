from unittest.mock import MagicMock
from harbor.core.dispatcher import Dispatcher
from harbor.core.config import HarborConfig, BackendConfig
from harbor.core.models import Service


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

    backends["caddy"].apply.assert_called_once_with(services)
    backends["envoy"].apply.assert_not_called()


def test_apply_with_authz_sidecar():
    config = make_config(envoy_features=["authz"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["authz"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    services = [make_service(sidecars=["my-bff"])]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once()
    backends["envoy"].apply.assert_called_once_with(services)


def test_apply_with_transcoder_sidecar():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    sidecar = make_sidecar(abilities=["transcoder"])
    dispatcher = make_dispatcher(config, backends, sidecars_for=[sidecar])

    services = [make_service(sidecars=["my-bff"])]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once()
    backends["envoy"].apply.assert_called_once_with(services)


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