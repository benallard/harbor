import pytest
from unittest.mock import MagicMock
from harbor.app import create_app
from harbor.core.models import Service


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.on_event = MagicMock()
    backend.apply = MagicMock()
    backend.register = MagicMock()
    backend.unregister = MagicMock()
    return backend


@pytest.fixture
def app(mock_backend, monkeypatch):
    monkeypatch.setattr("harbor.app.create_backend", lambda *a, **kw: mock_backend)
    
    import argparse
    args = argparse.Namespace(
        backend="caddy",
        backend_url="http://localhost:2019",
        backend_option=[],
        static_dir="tests/fixtures/routes.d",
    )
    app = create_app(args)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()