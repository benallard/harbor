from unittest.mock import MagicMock

from harbor.core.dispatcher import Dispatcher
from harbor.core.config import HarborConfig, BackendConfig
from harbor.core.models import Service


def make_config(delegate=None):
    return HarborConfig(
        ingress="caddy",
        backends={
            "caddy": BackendConfig(
                kind="caddy",
                url="http://localhost:2019",
                delegate=delegate or {},
            ),
            "envoy": BackendConfig(
                kind="envoy",
                url="",
                options={"listener-port": "10000"},
            ),
        },
    )


def make_backends():
    caddy = MagicMock()
    caddy.listener_url = "127.0.0.1:80"
    envoy = MagicMock()
    envoy.listener_url = "127.0.0.1:10000"
    return {"caddy": caddy, "envoy": envoy}


def make_service(kind="proxy"):
    return Service(
        id="svc1",
        prefix="/svc1",
        kind=kind,
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
    )


# --- apply ---


def test_apply_no_delegate():
    config = make_config()
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    services = [make_service("proxy")]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once_with(services)
    backends["envoy"].apply.assert_not_called()


def test_apply_with_delegate():
    config = make_config(delegate={"grpc": "envoy"})
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    services = [make_service("grpc")]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once()
    backends["envoy"].apply.assert_called_once_with(services)


# --- dispatch ---


def test_dispatch_no_delegate():
    config = make_config()
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service("proxy")
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()


def test_dispatch_with_delegate():
    config = make_config(delegate={"grpc": "envoy"})
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service("grpc")
    dispatcher.dispatch("registered", service)

    # caddy gets a transformed proxy service pointing at envoy
    caddy_call = backends["caddy"].on_event.call_args
    assert caddy_call[0][0] == "registered"
    transformed = caddy_call[0][1]
    assert transformed.kind == "proxy"
    assert transformed.upstreams == ["127.0.0.1:10000"]
    assert transformed.id == service.id
    assert transformed.prefix == service.prefix

    # envoy gets the original service unchanged
    backends["envoy"].on_event.assert_called_once_with("registered", service)


def test_dispatch_delegate_unregister():
    config = make_config(delegate={"grpc": "envoy"})
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service("grpc")
    dispatcher.dispatch("unregistered", service)

    backends["caddy"].on_event.assert_called_once()
    backends["envoy"].on_event.assert_called_once_with("unregistered", service)


def test_dispatch_transform_preserves_original():
    config = make_config(delegate={"grpc": "envoy"})
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service("grpc")
    dispatcher.dispatch("registered", service)

    # original service is untouched
    assert service.kind == "grpc"
    assert service.upstreams == ["127.0.0.1:9090"]


def test_dispatch_non_delegated_kind_goes_to_ingress_only():
    config = make_config(delegate={"grpc": "envoy"})
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service("proxy")
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()
