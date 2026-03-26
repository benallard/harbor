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


def make_service(bff=None, transcoder=None):
    return Service(
        id="svc1",
        prefix="/svc1",
        kind="proxy",
        upstreams=["127.0.0.1:9090"],
        source="dynamic",
        bff=bff,
        transcoder=transcoder,
    )


# --- apply ---


def test_apply_no_features():
    config = make_config()
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    services = [make_service()]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once_with(services)
    backends["envoy"].apply.assert_not_called()


def test_apply_with_bff():
    config = make_config(envoy_features=["bff"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    services = [make_service(bff={"enabled": True})]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once()
    backends["envoy"].apply.assert_called_once_with(services)


def test_apply_with_transcoder():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    services = [
        make_service(
            transcoder={
                "proto_descriptor": "/etc/harbor/proto/svc.pb",
                "services": ["svc.v1.Svc"],
            }
        )
    ]
    dispatcher.apply(services)

    backends["caddy"].apply.assert_called_once()
    backends["envoy"].apply.assert_called_once_with(services)


# --- dispatch ---


def test_dispatch_no_features():
    config = make_config()
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service()
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()


def test_dispatch_with_bff():
    config = make_config(envoy_features=["bff"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service(bff={"enabled": True})
    dispatcher.dispatch("registered", service)

    caddy_call = backends["caddy"].on_event.call_args
    assert caddy_call[0][0] == "registered"
    transformed = caddy_call[0][1]
    assert transformed.kind == "proxy"
    assert transformed.upstreams == ["127.0.0.1:10000"]
    assert transformed.id == service.id

    backends["envoy"].on_event.assert_called_once_with("registered", service)


def test_dispatch_with_transcoder():
    config = make_config(envoy_features=["transcoder"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service(
        transcoder={
            "proto_descriptor": "/etc/harbor/proto/svc.pb",
            "services": ["svc.v1.Svc"],
        }
    )
    dispatcher.dispatch("registered", service)

    caddy_call = backends["caddy"].on_event.call_args
    transformed = caddy_call[0][1]
    assert transformed.upstreams == ["127.0.0.1:10000"]

    backends["envoy"].on_event.assert_called_once_with("registered", service)


def test_dispatch_transform_preserves_original():
    config = make_config(envoy_features=["bff"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service(bff={"enabled": True})
    dispatcher.dispatch("registered", service)

    assert service.kind == "proxy"
    assert service.upstreams == ["127.0.0.1:9090"]
    assert service.bff == {"enabled": True}


def test_dispatch_unregister_with_bff():
    config = make_config(envoy_features=["bff"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service(bff={"enabled": True})
    dispatcher.dispatch("unregistered", service)

    backends["caddy"].on_event.assert_called_once()
    backends["envoy"].on_event.assert_called_once_with("unregistered", service)


def test_dispatch_no_features_goes_to_ingress_only():
    config = make_config(envoy_features=["bff", "transcoder"])
    backends = make_backends()
    dispatcher = Dispatcher(config, backends)

    service = make_service()
    dispatcher.dispatch("registered", service)

    backends["caddy"].on_event.assert_called_once_with("registered", service)
    backends["envoy"].on_event.assert_not_called()
