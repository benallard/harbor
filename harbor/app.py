import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

import argparse  # noqa: E402
from flask import Flask  # noqa: E402

from .core.registry import Registry  # noqa: E402
from .core.loader import load_services  # noqa: E402
from .proxy.factory import create_backend  # noqa: E402
from .tasks.gc import create_gc  # noqa: E402
from .api import services, catalog  # noqa: E402


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
        "--backend-url",
        default="unix:///run/caddy/admin.socket",
        help="Backend admin URL or socket",
    )

    parser.add_argument(
        "--backend-option",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        help="Backend-specific options (e.g. server-name=srv0)",
    )

    parser.add_argument(
        "--static-dir",
        default="/etc/harbor/routes.d",
        help="Directory for static route configs",
    )

    return parser.parse_args()


def create_app(args):
    app = Flask(__name__)
    static = load_services(args.static_dir)
    registry = Registry(static)
    backend = create_backend(app, args.backend, args.backend_url, args.backend_option)

    registry.subscribe(backend.on_event)
    registry.subscribe(catalog.notify_subscribers)

    # Initial load
    backend.apply(list(registry.static.values()))

    gc_thread = create_gc(registry)
    gc_thread.start()

    app.register_blueprint(services.create_bp(registry))
    app.register_blueprint(catalog.create_bp(registry))

    return app


def main():
    args = parse_args()
    app = create_app(args)
    app.run(host=args.host, port=args.port)
