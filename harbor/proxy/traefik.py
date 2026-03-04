import yaml
from pathlib import Path
from .base import ProxyBackend


class TraefikBackend(ProxyBackend):

    def __init__(self, config_file):
        self.config_file = Path(config_file)

    def apply(self, routes):

        data = {"http": {"routers": {}, "services": {}}}

        # convert routes to traefik objects here

        with open(self.config_file, "w") as f:
            yaml.dump(data, f)
