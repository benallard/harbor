import argparse
from flask import Flask

from .core.registry import Registry
from .core.loader import load_services
from .proxy.factory import create_backend
from .tasks.gc import create_gc
from .api import services, catalog


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
        default="unix:///run/caddy/admin.socket",
        help="Caddy Admin API URL or unix socket (default: unix:///run/caddy/admin.sock)",
    )

    parser.add_argument(
        "--caddy-server-name",
        default="srv0",
        help="Caddy server name to manage routes for (default: srv0)",
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
    backend = create_backend(
        app, args.backend, args.caddy_admin, args.caddy_server_name
    )

    registry.subscribe(backend.on_event)
    registry.subscribe(catalog.notify_subscribers)

    # Initial load
    backend.apply(list(registry.static.values()))

    gc_thread = create_gc(registry, backend)
    gc_thread.start()

    app.register_blueprint(services.create_bp(registry))
    app.register_blueprint(catalog.create_bp(registry))

    return app


def main():
    args = parse_args()
    app = create_app(args)
    app.run(host=args.host, port=args.port)
