from flask import Flask

from core.registry import Registry
from proxy.flask_proxy import FlaskProxyBackend
from proxy.caddy import CaddyBackend
from render.routes import render_routes

import config


app = Flask(__name__)

registry = Registry()


def create_backend():

    if config.PROXY_BACKEND == "flask":
        return FlaskProxyBackend(app)

    if config.PROXY_BACKEND == "caddy":
        return CaddyBackend(config.CADDY_ADMIN)


backend = create_backend()


def reload_proxy():

    services = registry.all_services()

    if config.PROXY_BACKEND == "flask":

        backend.apply(services)

    else:

        routes = render_routes(services)
        backend.apply(routes)