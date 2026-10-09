from unittest.mock import patch, MagicMock
from harbor.backend.flask_proxy import Router
from harbor.core.models import Service


def test_router_prefix_match():
    router = Router()
    services = [
        Service(id="grafana", prefix="/grafana", kind="proxy"),
        Service(id="api", prefix="/grafana/api", kind="proxy"),
    ]
    router.rebuild(services)
    service, sub = router.match("/grafana/api/users")
    assert service.id == "api"
    assert sub == "users"


def test_router_root_match():
    router = Router()
    services = [Service(id="root", prefix="/", kind="proxy")]
    router.rebuild(services)
    service, sub = router.match("/test")
    assert service.id == "root"
    assert sub == "test"


def test_gateway_proxy(flask_client):
    mock_response = MagicMock()
    mock_response.content = b'{"status": "ok"}'
    mock_response.status_code = 200
    mock_response.headers = {}

    with patch(
        "harbor.backend.flask_proxy.httpx.Client.request", return_value=mock_response
    ):
        resp = flask_client.get("/proxy/get")
        assert resp.status_code == 200


def test_gateway_not_found(flask_client):
    resp = flask_client.get("/nonexistent")
    assert resp.status_code == 404


def test_gateway_static(flask_client, tmp_path):
    (tmp_path / "hello.txt").write_text("hello")
    flask_client.post(
        "/services",
        json={
            "id": "tmp-static",
            "prefix": "/tmp-static",
            "kind": "static",
            "directory": str(tmp_path),
            "ttl": 60,
        },
    )
    resp = flask_client.get("/tmp-static/hello.txt")
    assert resp.status_code == 200


def _register_spa(flask_client, tmp_path):
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    flask_client.post(
        "/services",
        json={
            "id": "spa",
            "prefix": "/spa",
            "kind": "static",
            "directory": str(tmp_path),
            "spa": True,
            "ttl": 60,
        },
    )


def test_gateway_static_spa_serves_existing_file(flask_client, tmp_path):
    _register_spa(flask_client, tmp_path)
    resp = flask_client.get("/spa/assets/app.js")
    assert resp.status_code == 200
    assert resp.data == b"console.log(1)"


def test_gateway_static_spa_falls_back_to_index(flask_client, tmp_path):
    _register_spa(flask_client, tmp_path)
    resp = flask_client.get("/spa/config/general")
    assert resp.status_code == 200
    assert resp.data == b"<html>spa</html>"
    assert resp.headers["Cache-Control"] == "no-cache"


def test_gateway_static_spa_missing_asset_is_404(flask_client, tmp_path):
    _register_spa(flask_client, tmp_path)
    resp = flask_client.get("/spa/assets/index-old.js")
    assert resp.status_code == 404


def test_gateway_static_without_spa_does_not_fall_back(flask_client, tmp_path):
    (tmp_path / "index.html").write_text("<html>spa</html>")
    flask_client.post(
        "/services",
        json={
            "id": "nospa",
            "prefix": "/nospa",
            "kind": "static",
            "directory": str(tmp_path),
            "ttl": 60,
        },
    )
    resp = flask_client.get("/nospa/config/general")
    assert resp.status_code == 404
