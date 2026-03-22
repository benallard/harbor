import yaml
from pathlib import Path
from .models import Service
import logging

logger = logging.getLogger(__name__)


def load_service(path: Path) -> Service:
    data = yaml.safe_load(path.read_text())
    return Service.from_dict(data, "file")


def load_services(path):
    services = {}
    for f in Path(path).glob("*.route"):
        try:
            service = load_service(f)
            logger.info("Loaded static service: %s at %s", service.id, service.prefix)
            services[service.id] = service
        except Exception as e:
            logger.warning("Skipping %s: %s", f.name, e)
    return services
