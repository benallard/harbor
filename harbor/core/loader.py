import yaml
from pathlib import Path
from .models import Service


def load_services(path):

    services = {}

    for f in Path(path).glob("*.yaml"):

        data = yaml.safe_load(open(f))

        service = Service.from_dict(data, "file")

        services[service.id] = service

    return services
