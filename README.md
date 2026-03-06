# Harbor

Harbor is a lightweight service registry and reverse proxy controller designed for single-host environments. It exposes services under path prefixes and manages proxy configuration dynamically, with support for both static and ephemeral services.

---

## How it works

Harbor sits alongside your reverse proxy and manages its configuration via API. Services can be declared statically via configuration files, or registered dynamically at runtime with a TTL lease. When a lease expires, Harbor automatically removes the route.

A built-in SPA dashboard lists all public services and updates in real time via SSE.

### Typical deployment

```
Client → Caddy → Service
```

Harbor manages Caddy's routes via the Caddy Admin API, leaving all traffic to flow directly through Caddy.

### Embedded proxy (development)

```
Client → Harbor (Flask backend) → Service
```

Harbor can act as the proxy itself, useful for local development without a separate Caddy instance.

---

## Service model

Services are exposed under a path prefix and come in two kinds:

- `proxy` — reverse proxies requests to one or more upstreams
- `static` — serves files from a local directory

Example static configuration (`/etc/harbor/services.d/grafana.yaml`):

```yaml
id: grafana
name: Grafana
kind: proxy
prefix: /grafana
upstreams:
  - 127.0.0.1:3000
icon: /assets/grafana.png
```

---

## Dynamic services

Dynamic services are registered via the internal API and expire unless renewed.

**Register a service:**

```
POST /services
Content-Type: application/json

{
  "id": "preview-123",
  "prefix": "/preview/123",
  "type": "proxy",
  "upstreams": ["127.0.0.1:5100"],
  "ttl": 60
}
```

Response:

```json
{
  "id": "preview-123",
  "lease": "<token>",
  "ttl": 60
}
```

**Renew a lease:**

```
POST /services/<id>/renew
Authorization: <lease-token>
```

**Unregister a service:**

```
DELETE /services/<id>
```

If a lease is not renewed before it expires, Harbor removes the route automatically.

---

## Public catalog API

The catalog API is intended for the SPA dashboard and other public consumers.

**List all public services:**

```
GET /catalog
```

**Get a service icon:**

```
GET /catalog/icon/<service-id>
```

**Subscribe to live updates (SSE):**

```
GET /catalog/stream
```

Events: `registered`, `unregistered`, `expired`. Each event carries the full service object.

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `HARBOR_BACKEND` | Proxy backend (`caddy`, `flask`) | `caddy` |
| `HARBOR_CADDY_ADMIN` | Caddy admin URL or unix socket | `http://127.0.0.1:2019` |
| `HARBOR_HOST` | Host to bind Harbor on | `0.0.0.0` |
| `HARBOR_PORT` | Port to bind Harbor on | `8080` |

For unix socket support, use `unix:///run/caddy/admin.sock` as the Caddy admin URL.

---

## Caddy configuration

Harbor expects Caddy to be running with the admin API enabled and accessible via a unix socket. Place the following in `/etc/caddy/Caddyfile`:

```caddyfile
{
    admin unix//run/caddy/admin.sock
}

:80 {
    try_files {path} /index.html
    file_server {
        root /var/www/bridge
    }
}
```

This configures the admin API on a unix socket and serves the Bridge SPA as a catch-all fallback. Harbor's service routes are more specific and will always take priority over the catch-all regardless of insertion order.

Set `HARBOR_CADDY_ADMIN` accordingly:

```
HARBOR_CADDY_ADMIN=unix:///run/caddy/admin.sock
```

Harbor's process user must have access to the socket. The simplest way is to add it to the `caddy` group:

```bash
usermod -aG caddy <harbor-user>
```

---

## Installation

```
poetry install
```

Run Harbor:

```
poetry run harbor
```

Run with embedded proxy (development):

```
HARBOR_BACKEND=flask poetry run harbor
```

---

## Deployment with Gunicorn

SSE requires a threaded worker model. Recommended invocation:

```
gunicorn -k gthread --workers 1 --threads 16 harbor:app
```

Single worker is required to keep the in-process SSE subscriber list consistent across connections.

---

## Development

```
poetry run pytest
poetry run black .
poetry run ruff check .
```

---

## Project structure

```
harbor/
  api/        REST API blueprints (services, catalog)
  core/       registry, leases, models, GC
  proxy/      proxy backends (caddy, flask)
tests/
```

---

## License

MIT