import pytest
from harbor.core.models import Service


def make_dynamic_service(id="dyn-1", prefix="/dynamic", kind="proxy"):
    return {
        "id": id,
        "prefix": prefix,
        "kind": kind,
        "upstreams": ["127.0.0.1:9000"] if kind == "proxy" else None,
        "ttl": 30,
    }


# --- Catalog ---

def test_catalog_returns_public_services(client):
    response = client.get("/catalog")
    assert response.status_code == 200
    data = response.get_json()
    ids = [s["id"] for s in data]
    assert "test-proxy" in ids
    assert "test-static" in ids


def test_catalog_excludes_private_services(client):
    response = client.get("/catalog")
    data = response.get_json()
    ids = [s["id"] for s in data]
    assert "test-private" not in ids


def test_catalog_service_fields(client):
    response = client.get("/catalog")
    data = response.get_json()
    service = next(s for s in data if s["id"] == "test-proxy")
    assert "id" in service
    assert "name" in service
    assert "prefix" in service
    assert "icon" in service
    assert "upstreams" not in service
    assert "directory" not in service


def test_catalog_icon_not_found(client):
    response = client.get("/catalog/icon/nonexistent")
    assert response.status_code == 404


def test_catalog_icon_no_icon(client):
    response = client.get("/catalog/icon/test-proxy")
    assert response.status_code == 404

@pytest.mark.skip(reason="SSE hangs with Flask test client")
def test_catalog_stream_content_type(client):
    response = client.get("/catalog/stream")
    assert response.content_type == "text/event-stream"


# --- Services ---

def test_create_service(client, mock_backend):
    response = client.post("/services", json=make_dynamic_service())
    assert response.status_code == 201
    data = response.get_json()
    assert data["id"] == "dyn-1"
    assert "lease" in data
    assert data["ttl"] == 30


def test_create_service_missing_fields(client):
    response = client.post("/services", json={"id": "incomplete"})
    assert response.status_code == 400


def test_create_service_triggers_backend(client, mock_backend):
    client.post("/services", json=make_dynamic_service())
    mock_backend.on_event.assert_called_once()
    event, service = mock_backend.on_event.call_args[0]
    assert event == "registered"
    assert service.id == "dyn-1"


def test_delete_service(client, mock_backend):
    client.post("/services", json=make_dynamic_service())
    response = client.delete("/services/dyn-1")
    assert response.status_code == 200


def test_delete_service_not_found(client):
    response = client.delete("/services/nonexistent")
    assert response.status_code == 404


def test_delete_service_triggers_backend(client, mock_backend):
    client.post("/services", json=make_dynamic_service())
    mock_backend.on_event.reset_mock()
    client.delete("/services/dyn-1")
    mock_backend.on_event.assert_called_once()
    event, service = mock_backend.on_event.call_args[0]
    assert event == "unregistered"
    assert service.id == "dyn-1"


def test_renew_valid_token(client):
    response = client.post("/services", json=make_dynamic_service())
    token = response.get_json()["lease"]
    response = client.post("/services/dyn-1/renew", headers={"Authorization": token})
    assert response.status_code == 200


def test_renew_wrong_token(client):
    client.post("/services", json=make_dynamic_service())
    response = client.post("/services/dyn-1/renew", headers={"Authorization": "wrong"})
    assert response.status_code == 403


def test_renew_missing_token(client):
    client.post("/services", json=make_dynamic_service())
    response = client.post("/services/dyn-1/renew")
    assert response.status_code == 401


def test_renew_nonexistent_service(client):
    response = client.post("/services/nonexistent/renew", headers={"Authorization": "any"})
    assert response.status_code == 403