import requests
import json
from .base import ProxyBackend


class CaddyBackend(ProxyBackend):

    def __init__(self, admin_url):
        self.admin_url = admin_url

    def apply(self, routes):

        config = {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":80"],
                            "routes": routes
                        }
                    }
                }
            }
        }

        requests.post(
            f"{self.admin_url}/config",
            json=config
        )