import requests
import requests_unixsocket
from typing import List
from .base import ProxyBackend
from ..core.models import Service


class CaddyBackend(ProxyBackend):

    def __init__(self, admin_url):
        self.admin_url = admin_url
        if admin_url.startswith("http+unix://"):
            self.session = requests_unixsocket.Session()
        else:
            self.session = requests.Session()

    def apply(self, services):

        routes = render_routes(services)
        config = {
            "apps": {
                "http": {"servers": {"srv0": {"listen": [":80"], "routes": routes}}}
            }
        }

        self.session.post(f"{self.admin_url}/config", json=config)


def render_routes(services: List[Service]):
    routes = []

    for s in services:
        if s.kind == "proxy":
            # If public_paths is set, use it; otherwise, proxy everything under prefix
            paths = s.public_paths or [f"{s.prefix}*"]

            route = {
                "match": [{"path": paths}],
                "handle": [
                    {
                        "handler": "reverse_proxy",
                        "upstreams": [
                            {"dial": upstream} for upstream in (s.upstreams or [])
                        ],
                    }
                ],
            }

            routes.append(route)

        elif s.kind == "static":
            route = {
                "match": [{"path": [f"{s.prefix}*"]}],
                "handle": [{"handler": "file_server", "root": s.directory}],
            }
            routes.append(route)

    return routes
