import requests
from .base import ProxyBackend


class CaddyBackend(ProxyBackend):

    def __init__(self, admin_url):
        self.admin_url = admin_url

    def apply(self, services):

        routes = render_routes(services)
        config = {
            "apps": {
                "http": {"servers": {"srv0": {"listen": [":80"], "routes": routes}}}
            }
        }

        requests.post(f"{self.admin_url}/config", json=config)


def render_routes(services):

    routes = []

    for s in services:

        if s.kind == "proxy":

            routes.append(
                {
                    "match": [{"path": [f"{s.prefix}*"]}],
                    "handle": [
                        {
                            "handler": "reverse_proxy",
                            "upstreams": [{"dial": u} for u in s.upstreams],
                        }
                    ],
                }
            )

    return routes
