import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

import argparse  # noqa: E402
from flask import Flask  # noqa: E402
import os  # noqa: E402

from .core.registry import Registry  # noqa: E402
from .core.loader import load_services  # noqa: E402
from .backend.factory import create_backend  # noqa: E402
from .tasks.gc import create_gc  # noqa: E402
from .tasks.watcher import create_watcher  # noqa: E402
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
        dest="backend_options",
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

def default_config():
    return argparse.Namespace(
        backend=os.environ.get("HARBOR_BACKEND", "caddy"),
        backend_url=os.environ.get("HARBOR_BACKEND_URL", "unix:///run/caddy/admin.socket"),
        backend_options=os.environ.get("HARBOR_BACKEND_OPTIONS", "").split() or [],
        static_dir=os.environ.get("HARBOR_STATIC_DIR", "/etc/harbor/routes.d"),
        host=os.environ.get("HARBOR_HOST", "0.0.0.0"),
        port=int(os.environ.get("HARBOR_PORT", "8080")),
    )

def create_app(args=None):
    if args is None:
        args = default_config()
    app = Flask(__name__)
    static = load_services(args.static_dir)
    registry = Registry(static)
    backend = create_backend(app, args.backend, args.backend_url, args.backend_options)

    registry.subscribe(backend.on_event)
    registry.subscribe(catalog.notify_subscribers)

    # Initial load
    backend.apply(list(registry.static.values()))

    gc_thread = create_gc(registry)
    gc_thread.start()

    watcher = create_watcher(registry, args.static_dir)
    watcher.start()

    app.register_blueprint(services.create_bp(registry))
    app.register_blueprint(catalog.create_bp(registry))

    return app


def main():
    args = parse_args()
    app = create_app(args)
    app.run(host=args.host, port=args.port)
