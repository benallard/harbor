import yaml
from pathlib import Path
from .models import Service


def load_services(path):

    services = {}

    for f in Path(path).glob("*.yaml"):

        data = yaml.safe_load(open(f))

        service = Service(
            id=data["name"],
            prefix=data["prefix"],
            kind=data["type"],
            upstreams=data.get("upstreams"),
            directory=data.get("directory"),
            name=data.get("name"),
            icon=data.get("icon"),
            source="file",
        )

        services[service.id] = service

    return services
