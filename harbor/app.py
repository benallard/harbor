import argparse
from flask import Flask

from .core.registry import Registry
from .core.loader import load_services
from .proxy.factory import create_backend


def parse_args():
    parser = argparse.ArgumentParser(
        description="Harbor – dynamic service registry and proxy manager"
    )

    parser.add_argument(
        "--backend",
        default="caddy",
        choices=["caddy", "flask"],
        help="Proxy backend to use (default: caddy)",
    )

    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to listen on (default: 0.0.0.0)"
    )

    parser.add_argument(
        "--port", type=int, default=8080, help="Port to listen on (default: 8080)"
    )

    parser.add_argument(
        "--caddy-admin",
        default="http://127.0.0.1:2019",
        help="Caddy Admin API URL (default: http://127.0.0.1:2019)",
    )

    parser.add_argument(
        "--static-dir",
        default="/etc/harbor/service.d",
        help="Directory for static service configs",
    )

    return parser.parse_args()


def create_app(args):

    app = Flask(__name__)

    static = load_services(args.static_dir)

    registry = Registry(static)

    backend = create_backend(app, args.backend, args.caddy_admin)

    def reload_proxy():

        services = registry.all_services()
        backend.apply(services)

    # attach runtime objects
    app.registry = registry
    app.backend = backend
    app.reload_proxy = reload_proxy

    # initial load
    reload_proxy()

    return app


def main():
    args = parse_args()

    app = create_app(args)
    app.run(host=args.host, port=args.port)
