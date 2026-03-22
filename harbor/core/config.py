import argparse
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import yaml

logger = logging.getLogger(__name__)


@dataclass
class BackendConfig:
    kind: str
    url: str
    options: Dict[str, str] = field(default_factory=dict)
    delegate: Dict[str, str] = field(default_factory=dict)


@dataclass
class HarborConfig:
    static_dir: str = "/etc/harbor/routes.d"
    host: str = "0.0.0.0"
    port: int = 8080
    ingress: str = "default"
    backends: Dict[str, BackendConfig] = field(default_factory=dict)

    @staticmethod
    def from_file(path: str) -> "HarborConfig":
        data = yaml.safe_load(Path(path).read_text())
        backends = {
            name: BackendConfig(
                kind=cfg["kind"],
                url=cfg["url"],
                options=cfg.get("options", {}),
                delegate=cfg.get("delegate", {}),
            )
            for name, cfg in data.get("backends", {}).items()
        }
        return HarborConfig(
            static_dir=data.get("static_dir", "/etc/harbor/routes.d"),
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 8080),
            ingress=data.get("ingress", "default"),
            backends=backends,
        )

    @staticmethod
    def from_env() -> "HarborConfig":
        backends = {}
        backend_kind = os.environ.get("HARBOR_BACKEND", "caddy")
        backend_url = os.environ.get(
            "HARBOR_BACKEND_URL", "unix:///run/caddy/admin.socket"
        )
        backend_opts = dict(
            o.split("=", 1)
            for o in os.environ.get("HARBOR_BACKEND_OPTIONS", "").split()
            if "=" in o
        )
        backends["default"] = BackendConfig(
            kind=backend_kind,
            url=backend_url,
            options=backend_opts,
        )
        return HarborConfig(
            static_dir=os.environ.get("HARBOR_STATIC_DIR", "/etc/harbor/routes.d"),
            host=os.environ.get("HARBOR_HOST", "0.0.0.0"),
            port=int(os.environ.get("HARBOR_PORT", "8080")),
            ingress="default",
            backends=backends,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harbor – dynamic service registry and proxy manager"
    )
    parser.add_argument("--config", help="Path to Harbor config file")
    parser.add_argument("--backend", default=None, choices=["caddy", "flask"])
    parser.add_argument("--backend-url", dest="backend_url", default=None)
    parser.add_argument(
        "--backend-option", dest="backend_options", action="append", default=[]
    )
    parser.add_argument("--static-dir", dest="static_dir", default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def load_config() -> HarborConfig:
    args = parse_args()

    # config file takes precedence over env
    if args.config:
        logger.info("Loading config from %s", args.config)
        config = HarborConfig.from_file(args.config)
    elif "HARBOR_CONFIG" in os.environ:
        logger.info("Loading config from %s", os.environ["HARBOR_CONFIG"])
        config = HarborConfig.from_file(os.environ["HARBOR_CONFIG"])
    else:
        logger.info("Loading config from environment")
        config = HarborConfig.from_env()

    # CLI args override anything
    if args.backend:
        config.backends["default"].kind = args.backend
    if args.backend_url:
        config.backends["default"].url = args.backend_url
    if args.static_dir:
        config.static_dir = args.static_dir
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    return config
