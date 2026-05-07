import logging
from pathlib import Path
from typing import Optional


from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)
from watchdog.observers import Observer

from ..core.registry import Registry
from ..core.loader import load_service
from ..core.models import Service

logger = logging.getLogger(__name__)


class RouteFileHandler(FileSystemEventHandler):

    def __init__(self, registry: Registry):
        self.registry = registry
        self._route_ids = {}

    def _is_route_file(self, path: str) -> bool:
        return path.endswith(".route")

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        if not self._is_route_file(event.src_path):
            return
        self._upsert_path(event.src_path, "new")

    def on_modified(self, event: FileModifiedEvent):
        if event.is_directory:
            return
        if not self._is_route_file(event.src_path):
            return
        self._upsert_path(event.src_path, "modified")

    def on_deleted(self, event: FileDeletedEvent):
        if event.is_directory:
            return
        if not self._is_route_file(event.src_path):
            return
        service_id = self._route_ids.pop(event.src_path, Path(event.src_path).stem)
        logger.info("Watcher: route file deleted %s", event.src_path)
        self.registry.remove_static(service_id)

    def on_moved(self, event: FileMovedEvent):
        if event.is_directory:
            return

        if self._is_route_file(event.src_path):
            source_id = self._route_ids.pop(event.src_path, Path(event.src_path).stem)
            logger.info("Watcher: route file moved away %s", event.src_path)
            self.registry.remove_static(source_id)

        if not self._is_route_file(event.dest_path):
            return

        self._upsert_path(event.dest_path, "moved to")

    def _upsert_path(self, path: str, action: str) -> None:
        service = self._load(path)
        if not service:
            return

        previous_id = self._route_ids.get(path)
        if previous_id and previous_id != service.id:
            logger.info("Watcher: route id changed %s -> %s", previous_id, service.id)
            self.registry.remove_static(previous_id)

        logger.info("Watcher: %s %s %s", service.kind, action, service.id)
        self._route_ids[path] = service.id
        self.registry.add_static(service)

    def _load(self, path: str) -> Optional[Service]:
        try:
            return load_service(Path(path))
        except Exception as e:
            logger.warning("Watcher: failed to load %s: %s", path, e)
            return None


def create_watcher(registry: Registry, static_dir: str) -> Observer:
    p = Path(static_dir)
    if not p.exists():
        logger.warning("Static dir %s does not exist, watcher not started", static_dir)
        return None
    handler = RouteFileHandler(registry)
    observer = Observer()
    observer.schedule(handler, static_dir, recursive=False)
    return observer
