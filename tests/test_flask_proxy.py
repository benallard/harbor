import pytest

from harbor.app import create_app
from harbor.core.models import Service


@pytest.fixture
def app():

    app = create_app()

    service = Service(
        id="test", prefix="/test", kind="proxy", upstreams=["http://httpbin.org"]
    )

    app.backend.apply([service])

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_gateway_route(client):

    resp = client.get("/test/get")

    assert resp.status_code == 200
