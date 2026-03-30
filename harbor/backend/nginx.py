from ..core.config import HarborConfig
from .base import ProxyBackend


class NginxBackend(ProxyBackend):

    def __init__(self, config: HarborConfig):
        self.config_file = config.url


def render_nginx(services):
    raise NotImplementedError("Not yet")
