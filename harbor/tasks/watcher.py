import logging
from pathlib import Path


from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
)
from watchdog.observers import Observer

from ..core.registry import Registry
from ..core.loader import load_service
from ..core.models import Service

logger = logging.getLogger(__name__)


class RouteFileHandler(FileSystemEventHandler):

    def __init__(self, registry: Registry):
        self.registry = registry

    def _is_route_file(self, path: str) -> bool:
        return path.endswith(".route")

    def on_created(self, event: FileCreatedEvent):
        if not self._is_route_file(event.src_path):
            return
        service = self._load(event.src_path)
        if service:
            logger.info("Watcher: new %s %s", service.kind, service.id)
            self.registry.add_static(service)

    def on_modified(self, event: FileModifiedEvent):
        if not self._is_route_file(event.src_path):
            return
        service = self._load(event.src_path)
        if service:
            logger.info("Watcher: %s modified %s", service.kind, service.id)
            self.registry.add_static(service)

    def on_deleted(self, event: FileDeletedEvent):
        if not self._is_route_file(event.src_path):
            return
        service_id = Path(event.src_path).stem
        logger.info("Watcher: route file deleted %s", event.src_path)
        self.registry.remove_static(service_id)

    def _load(self, path: str) -> Service:
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
