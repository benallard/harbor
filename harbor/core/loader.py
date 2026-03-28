from typing import Dict
import yaml
from pathlib import Path
import logging

from .models import Service

logger = logging.getLogger(__name__)


def load_service(path: Path) -> Service:
    data = yaml.safe_load(path.read_text())
    return Service.from_dict(data, "file")


def load_services(path: str) -> Dict[str, Service]:
    services = {}
    for f in Path(path).glob("*.route"):
        try:
            service = load_service(f)
            if service.kind == "sidecar":
                logger.info("Loaded sidecar: %s", service.id)
            else:
                logger.info(
                    "Loaded static service: %s at %s", service.id, service.prefix
                )
            services[service.id] = service
        except Exception as e:
            logger.warning("Skipping %s: %s", f.name, e)
    return services
