import logging
import threading
import time

from ..core.registry import Registry

logger = logging.getLogger(__name__)


def create_gc(registry: Registry) -> threading.Thread:
    def run():
        while True:
            time.sleep(10)
            expired = registry.remove_expired()
            for service in expired:
                logger.info("GC: removed expired service %s", service.id)

    return threading.Thread(target=run, daemon=True)
