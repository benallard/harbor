from unittest.mock import MagicMock

from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileMovedEvent

from harbor.core.models import Service
from harbor.tasks.watcher import RouteFileHandler


def make_service(service_id="svc1"):
    return Service(
        id=service_id,
        kind="proxy",
        prefix="/svc1",
        upstreams=["127.0.0.1:8080"],
        source="file",
    )


def test_on_created_registers_route_file(monkeypatch):
    registry = MagicMock()
    handler = RouteFileHandler(registry)
    service = make_service("created-svc")

    monkeypatch.setattr("harbor.tasks.watcher.load_service", lambda _: service)

    handler.on_created(FileCreatedEvent("/etc/harbor/routes.d/created-svc.route"))

    registry.add_static.assert_called_once_with(service)


def test_on_moved_dpkg_new_to_route_registers(monkeypatch):
    registry = MagicMock()
    handler = RouteFileHandler(registry)
    service = make_service("oee-agent-web")

    monkeypatch.setattr("harbor.tasks.watcher.load_service", lambda _: service)

    handler.on_moved(
        FileMovedEvent(
            "/etc/harbor/routes.d/oee-agent-web.route.dpkg-new",
            "/etc/harbor/routes.d/oee-agent-web.route",
        )
    )

    registry.remove_static.assert_not_called()
    registry.add_static.assert_called_once_with(service)


def test_on_deleted_uses_service_id_from_loaded_file(monkeypatch):
    registry = MagicMock()
    handler = RouteFileHandler(registry)
    service = make_service("different-service-id")

    monkeypatch.setattr("harbor.tasks.watcher.load_service", lambda _: service)

    handler.on_created(FileCreatedEvent("/etc/harbor/routes.d/file-name.route"))
    handler.on_deleted(FileDeletedEvent("/etc/harbor/routes.d/file-name.route"))

    registry.remove_static.assert_called_once_with("different-service-id")


def test_on_moved_route_to_backup_unregisters(monkeypatch):
    registry = MagicMock()
    handler = RouteFileHandler(registry)
    service = make_service("different-service-id")

    monkeypatch.setattr("harbor.tasks.watcher.load_service", lambda _: service)

    handler.on_created(FileCreatedEvent("/etc/harbor/routes.d/file-name.route"))
    registry.reset_mock()

    handler.on_moved(
        FileMovedEvent(
            "/etc/harbor/routes.d/file-name.route",
            "/etc/harbor/routes.d/file-name.route.dpkg-old",
        )
    )

    registry.remove_static.assert_called_once_with("different-service-id")
    registry.add_static.assert_not_called()


def test_on_moved_route_to_route_reloads(monkeypatch):
    registry = MagicMock()
    handler = RouteFileHandler(registry)
    service = make_service("new-id")

    monkeypatch.setattr("harbor.tasks.watcher.load_service", lambda _: service)

    handler.on_moved(
        FileMovedEvent(
            "/etc/harbor/routes.d/old-id.route",
            "/etc/harbor/routes.d/new-id.route",
        )
    )

    registry.remove_static.assert_called_once_with("old-id")
    registry.add_static.assert_called_once_with(service)
