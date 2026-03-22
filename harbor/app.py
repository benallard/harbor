import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from flask import Flask  # noqa: E402
from .core.config import HarborConfig, load_config  # noqa: E402
from .core.dispatcher import Dispatcher  # noqa: E402
from .core.registry import Registry  # noqa: E402
from .core.loader import load_services  # noqa: E402
from .backend.factory import create_backend  # noqa: E402
from .tasks.gc import create_gc  # noqa: E402
from .tasks.watcher import create_watcher  # noqa: E402
from .api import services, catalog  # noqa: E402


def create_app(config: HarborConfig = None):
    if config is None:
        config = load_config()

    app = Flask(__name__)
    static = load_services(config.static_dir)
    registry = Registry(static)

    # create all backends
    backend_instances = {
        name: create_backend(app, name, backend_config)
        for name, backend_config in config.backends.items()
    }

    # build dispatcher and subscribe it to registry
    dispatcher = Dispatcher(config, backend_instances)
    registry.subscribe(dispatcher.dispatch)
    registry.subscribe(catalog.notify_subscribers)

    # apply static services
    dispatcher.apply(list(registry.static.values()))

    gc_thread = create_gc(registry)
    gc_thread.start()

    watcher = create_watcher(registry, config.static_dir)
    if watcher:
        watcher.start()

    app.register_blueprint(services.create_bp(registry))
    app.register_blueprint(catalog.create_bp(registry))

    return app


def main():
    config = load_config()
    app = create_app(config)
    app.run(host=config.host, port=config.port)
