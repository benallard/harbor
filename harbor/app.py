from flask import Flask

from . import config
from .core.registry import Registry
from .proxy.factory import create_backend
from .render.routes import render_routes


def create_app():

    app = Flask(__name__)

    registry = Registry()

    backend = create_backend(app)

    def reload_proxy():

        services = registry.all_services()

        if config.PROXY_BACKEND == "flask":

            backend.apply(services)

        else:

            routes = render_routes(services)
            backend.apply(routes)

    # attach runtime objects
    app.registry = registry
    app.backend = backend
    app.reload_proxy = reload_proxy

    # initial load
    reload_proxy()

    return app


def main():

    app = create_app()

    app.run(
        host=config.HOST,
        port=config.PORT
    )