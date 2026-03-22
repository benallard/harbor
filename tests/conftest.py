import pytest
from unittest.mock import MagicMock
from harbor.app import create_app
from harbor.core.config import HarborConfig, BackendConfig


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.listener_url = "127.0.0.1:80"
    return backend


@pytest.fixture
def app(monkeypatch, mock_backend):
    # Patch it were it's being used, not where it's defined
    monkeypatch.setattr(
        "harbor.app.create_backend", lambda app, name, config: mock_backend
    )
    config = HarborConfig(
        static_dir="tests/fixtures/routes.d",
        backends={"default": BackendConfig(kind="caddy", url="http://localhost:2019")},
        ingress="default",
    )
    app = create_app(config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def flask_app():
    config = HarborConfig(
        static_dir="tests/fixtures/routes.d",
        backends={"default": BackendConfig(kind="flask", url="")},
        ingress="default",
    )
    app = create_app(config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def flask_client(flask_app):
    return flask_app.test_client()
