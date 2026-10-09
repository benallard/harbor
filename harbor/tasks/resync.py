import logging
import threading
import time
from typing import Iterable

from ..backend.base import ProxyBackend

logger = logging.getLogger(__name__)

RESYNC_INTERVAL_S = 10


def create_resync(backends: Iterable[ProxyBackend]) -> threading.Thread:
    backends = list(backends)

    def run():
        while True:
            time.sleep(RESYNC_INTERVAL_S)
            for backend in backends:
                try:
                    backend.resync()
                except Exception:
                    logger.exception("Resync of %s failed", backend)

    return threading.Thread(target=run, daemon=True)
