import os


PROXY_BACKEND = os.getenv("HARBOR_BACKEND", "caddy")

CADDY_ADMIN = os.getenv("HARBOR_CADDY_ADMIN", "http://127.0.0.1:2019")

STATIC_CONFIG_DIR = os.getenv("HARBOR_STATIC_DIR", "/etc/harbor/service.d")

HOST = os.getenv("HARBOR_HOST", "0.0.0.0")
PORT = int(os.getenv("HARBOR_PORT", "8080"))
