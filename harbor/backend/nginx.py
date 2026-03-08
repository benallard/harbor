import subprocess
from .base import ProxyBackend


class NginxBackend(ProxyBackend):

    def __init__(self, config_file):
        self.config_file = config_file

    def apply(self, services):

        with open(self.config_file, "w") as f:
            f.write(render_nginx(services))

        subprocess.run(["nginx", "-s", "reload"])


def render_nginx(services):
    raise NotImplementedError("Not yet")
