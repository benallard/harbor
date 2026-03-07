from harbor.proxy.caddy import CaddyBackend
from harbor.proxy.flask_proxy import FlaskProxyBackend

def create_backend(app, backend, url, options):
    opts = dict(o.split("=", 1) for o in options)
    
    if backend == "caddy":
        return CaddyBackend(url, server_name=opts.get("server-name", "srv0"))
    
    if backend == "flask":
        return FlaskProxyBackend(app)
    
    raise RuntimeError(f"Unsupported backend: {backend}")