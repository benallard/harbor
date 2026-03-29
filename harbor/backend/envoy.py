import logging
import os
import json
from pathlib import Path

from dataclasses import dataclass
from .base import ProxyBackend
from ..core.models import Service
from ..core.config import BackendConfig

logger = logging.getLogger(__name__)

ENVOY_RUN_DIR = Path("/run/envoy")
CDS_PATH = ENVOY_RUN_DIR / "cds.yaml"
LDS_PATH = ENVOY_RUN_DIR / "lds.yaml"


@dataclass
class EnvoyConfig:
    listener_port: int = 10000
    admin_port: int = 9901

    @staticmethod
    def from_backend_config(config: BackendConfig) -> "EnvoyConfig":
        return EnvoyConfig(
            listener_port=int(config.options.get("listener-port", 10000)),
            admin_port=int(config.options.get("admin-port", 9901)),
        )


class EnvoyBackend(ProxyBackend):

    def __init__(self, config: BackendConfig):
        self.config = EnvoyConfig.from_backend_config(config)
        self.clusters = {}  # service_id → cluster config
        self.routes = {}  # service_id → route config
        self.authz_cluster = None  # service_id of the cluster to use for authz
        ENVOY_RUN_DIR.mkdir(parents=True, exist_ok=True)

    def apply(self, services):
        for service in services:
            self._add(service)
        self._write()

    def register(self, service: Service):
        self._add(service)
        self._write()

    def unregister(self, service: Service):
        self.clusters.pop(service.id, None)
        self.routes.pop(service.id, None)
        if self.authz_cluster == service.id:
            self.authz_cluster = None
        self._write()

    def on_event(self, event: str, service: Service):
        if event == "registered":
            self.register(service)
        elif event in ("unregistered", "expired"):
            self.unregister(service)

    def _add(self, service: Service):
        if service.kind == "sidecar":
            self.clusters[service.id] = render_sidecar_cluster(service)
            if "authz" in (service.abilities or []):
                self.authz_cluster = service.id
            return
        self.clusters[service.id] = render_cluster(service)
        self.routes[service.id] = render_route(service)

    def _write(self):
        _atomic_write(CDS_PATH, {"resources": list(self.clusters.values())})
        _atomic_write(
            LDS_PATH,
            {
                "resources": [
                    {
                        "@type": "type.googleapis.com/envoy.config.listener.v3.Listener",
                        "name": "harbor",
                        "address": {
                            "socket_address": {
                                "address": "0.0.0.0",
                                "port_value": int(self.config.listener_port),
                            }
                        },
                        "filter_chains": [
                            {
                                "filters": [
                                    {
                                        "name": "envoy.filters.network.http_connection_manager",
                                        "typed_config": {
                                            "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                                            "stat_prefix": "harbor",
                                            "http_filters": self._build_http_filters(),
                                            "route_config": {
                                                "virtual_hosts": [
                                                    {
                                                        "name": "local",
                                                        "domains": ["*"],
                                                        "routes": list(
                                                            self.routes.values()
                                                        ),
                                                    }
                                                ]
                                            },
                                        },
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )

    def _build_http_filters(self) -> list:
        filters = []

        if any(s.get("typed_per_filter_config") for s in self.routes.values()):
            filters.append(
                {
                    "name": "envoy.filters.http.grpc_json_transcoder",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.filters.http.grpc_json_transcoder.v3.GrpcJsonTranscoder",
                        "proto_descriptor": "",
                        "services": [],
                    },
                }
            )

        if self._has_authz():
            filters.append(
                {
                    "name": "envoy.filters.http.ext_authz",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz",
                        "grpc_service": {
                            "envoy_grpc": {"cluster_name": self.authz_cluster}
                        },
                    },
                }
            )

        filters.append(
            {
                "name": "envoy.filters.http.router",
                "typed_config": {
                    "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                },
            }
        )

        return filters

    def _has_authz(self) -> bool:
        return self.authz_cluster is not None


def _atomic_write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.rename(tmp, path)


def render_cluster(service: Service) -> dict:
    upstream = service.upstreams[0]
    host, port = upstream.rsplit(":", 1)

    cluster = {
        "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
        "name": service.id,
        "type": "STRICT_DNS",
        "load_assignment": {
            "cluster_name": service.id,
            "endpoints": [
                {
                    "lb_endpoints": [
                        {
                            "endpoint": {
                                "address": {
                                    "socket_address": {
                                        "address": host,
                                        "port_value": int(port),
                                    }
                                }
                            }
                        }
                    ]
                }
            ],
        },
    }

    if service.protocol == "http2":
        cluster["typed_extension_protocol_options"] = {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions",
                "explicit_http_config": {"http2_protocol_options": {}},
            }
        }

    return cluster


def render_route(service: Service) -> dict:
    route = {
        "match": {"prefix": service.prefix},
        "route": {
            "cluster": service.id,
        },
    }

    if service.transcoder:
        route["typed_per_filter_config"] = {
            "envoy.filters.http.grpc_json_transcoder": {
                "@type": "type.googleapis.com/envoy.extensions.filters.http.grpc_json_transcoder.v3.GrpcJsonTranscoder",
                "proto_descriptor": service.transcoder["proto_descriptor"],
                "services": service.transcoder["services"],
                "print_options": {
                    "add_whitespace": True,
                    "always_print_primitive_fields": True,
                },
            }
        }

    return route


def render_sidecar_cluster(sidecar: Service) -> dict:
    upstream = sidecar.upstreams[0]
    host, port = upstream.rsplit(":", 1)
    return {
        "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
        "name": sidecar.id,
        "type": "STRICT_DNS",
        "typed_extension_protocol_options": {
            "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                "@type": "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions",
                "explicit_http_config": {"http2_protocol_options": {}},
            }
        },
        "load_assignment": {
            "cluster_name": sidecar.id,
            "endpoints": [
                {
                    "lb_endpoints": [
                        {
                            "endpoint": {
                                "address": {
                                    "socket_address": {
                                        "address": host,
                                        "port_value": int(port),
                                    }
                                }
                            }
                        }
                    ]
                }
            ],
        },
    }
