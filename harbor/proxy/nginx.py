import subprocess
from .base import ProxyBackend


class NginxBackend(ProxyBackend):

    def __init__(self, config_file):
        self.config_file = config_file

    def apply(self, routes):

        with open(self.config_file, "w") as f:
            f.write(render_nginx(routes))

        subprocess.run(["nginx", "-s", "reload"])