from pathlib import Path

from ..core.config import HarborConfig
from .base import ProxyBackend


class TraefikBackend(ProxyBackend):

    def __init__(self, config: HarborConfig):
        self.config_file = Path(config.url)
