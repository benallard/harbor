# Harbor

Some services are always there — dependable, unmoving, like ships that never leave port.
Others come and go, appearing just long enough to do their job before disappearing again.
Harbor manages both, exposing them cleanly under a reverse proxy without you having to think about it.

Harbor is a lightweight service registry and proxy controller for single-host environments.
It registers routes with your reverse proxy at startup for static services, and adds or removes them on the fly as ephemeral services come and go.
When a lease expires, Harbor cleans up automatically.

A companion SPA — **Bridge** — provides a real-time dashboard of all public services, updated live via SSE.

---

## How it works

Harbor sits alongside your reverse proxy and manages its routing configuration via API.
It never handles traffic itself in production — it just tells the proxy what to route where.

```
Client → Caddy → Service
            ↑
          Harbor
```

Static services are declared in `.route` files and registered with Caddy at startup.
Ephemeral services register themselves via Harbor's internal API with a TTL lease, and are removed automatically when the lease expires or is not renewed.

### Embedded proxy mode

For local development, Harbor can act as the proxy itself:

```
Client → Harbor → Service
```

No Caddy required.
Useful for testing without a full proxy setup.

---

## Route configuration

Routes are declared as `.route` files in `/etc/harbor/routes.d/`.
Each file describes one service.

**Proxy route** — reverse proxies requests to one or more upstreams:

```yaml
id: grafana
name: Grafana
kind: proxy
prefix: /grafana
upstreams:
  - 127.0.0.1:3000
icon: /assets/grafana.png
```

**Static route** — serves files from a local directory:

```yaml
id: docs
name: Documentation
kind: static
prefix: /docs
directory: /srv/docs
```

**Restricting public paths** — only expose specific paths of a service:

```yaml
id: harbor
name: Harbor
kind: proxy
prefix: /harbor
upstreams:
  - 127.0.0.1:8080
public_paths:
  - /catalog
  - /catalog/*
public: true
```

Setting `public: false` hides a service from the Bridge catalog entirely.

---

## Ephemeral services

Ephemeral services register themselves via Harbor's internal API and expire unless renewed.

**Register:**

```
POST /services
Content-Type: application/json

{
  "id": "preview-abc",
  "prefix": "/preview/abc",
  "kind": "proxy",
  "upstreams": ["127.0.0.1:5100"],
  "ttl": 60
}
```

Response:

```json
{
  "id": "preview-abc",
  "lease": "<token>",
  "ttl": 60
}
```

**Renew:**

```
POST /services/<id>/renew
Authorization: <lease-token>
```

**Unregister:**

```
DELETE /services/<id>
```

If a lease expires without renewal, Harbor removes the route automatically and notifies Bridge via SSE.

---

## Bridge catalog API

Bridge consumes the catalog API to display the public service dashboard.

```
GET /catalog              — list all public services
GET /catalog/icon/<id>    — retrieve a service icon
GET /catalog/stream       — SSE stream of live updates
```

SSE events: `registered`, `unregistered`, `expired`.
Each event carries the full service object.
Bridge updates in real time without polling.

---

## Caddy configuration

Harbor manages Caddy's routes via the admin API over a unix socket.
Place the following in `/etc/caddy/Caddyfile`:

```caddyfile
{
    admin unix//run/caddy/admin.socket|0660
}

:80 {
    try_files {path} /index.html
    file_server {
        root /var/www/bridge
    }
}
```

The catch-all serves Bridge.
Harbor's service routes are more specific and always take priority regardless of insertion order.

Harbor's process user needs access to the socket:

```bash
sudo usermod -aG caddy <harbor-user>
```

---

## Running Harbor

```
poetry install
poetry run harbor
```

Key options:

```
--static-dir       Directory for .route files (default: /etc/harbor/routes.d)
--backend          Proxy backend: caddy or flask (default: caddy)
--backend-url      Backend admin URL or socket (default: unix:///run/caddy/admin.socket)
--backend-option   Backend-specific options, e.g. server-name=srv0
--host             Host to bind on (default: 0.0.0.0)
--port             Port to bind on (default: 8080)
```

Development mode with embedded proxy:

```
poetry run harbor --backend flask
```

---

## Deployment

SSE requires a threaded Gunicorn worker.
Single worker keeps the SSE subscriber list consistent:

```
gunicorn -k gthread --workers 1 --threads 16 harbor:app
```

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
  backend/    proxy backends (caddy, flask)
tests/
  fixtures/   static .route files for testing
```

---

## License

MIT