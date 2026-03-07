import yaml
from pathlib import Path
from .models import Service
import logging

logger = logging.getLogger(__name__)


def load_services(path):
    services = {}
    for f in Path(path).glob("*.route"):
        try:
            data = yaml.safe_load(f.read_text())
            service = Service.from_dict(data, "file")
            logger.info(
                "Loaded service %s at %s from %s", service.id, service.prefix, f
            )
            services[service.id] = service
        except KeyError as e:
            logger.error("Skipping %s: missing required field %s", f.name, e)
        except Exception as e:
            logger.error("Error loading %s: %s", f.name, e)

    return services
