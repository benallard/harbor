# Harbor

Some services are always there — dependable, unmoving, like ships that never leave port.
Others come and go, appearing just long enough to do their job before disappearing again.
Harbor manages both, exposing them cleanly under a reverse proxy without you having to think about it.

Harbor is a lightweight service registry and proxy controller for single-host environments.
It registers routes with your reverse proxy at startup for static services, and adds or removes them on the fly as ephemeral services come and go.
When a lease expires, Harbor cleans up automatically.

A companion SPA — **Gangway** — provides a real-time dashboard of all public services, updated live via SSE.

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

## Gangway catalog API

Gangway consumes the catalog API to display the public service dashboard.

```
GET /catalog              — list all public services
GET /catalog/icon/<id>    — retrieve a service icon
GET /catalog/stream       — SSE stream of live updates
```

SSE events: `registered`, `unregistered`, `expired`.
Each event carries the full service object.
Gangway updates in real time without polling.

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

The catch-all serves Gangway.
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

Key options — all available as CLI arguments or environment variables:

| CLI | Env | Default |
|---|---|---|
| `--backend` | `HARBOR_BACKEND` | `caddy` |
| `--backend-url` | `HARBOR_BACKEND_URL` | `unix:///run/caddy/admin.socket` |
| `--backend-option` | `HARBOR_BACKEND_OPTIONS` | — |
| `--static-dir` | `HARBOR_STATIC_DIR` | `/etc/harbor/routes.d` |
| `--host` | `HARBOR_HOST` | `0.0.0.0` |
| `--port` | `HARBOR_PORT` | `8080` |

Development mode with embedded proxy:

```
poetry run harbor --backend flask
```

---

## Deployment

Harbor is designed to run under Gunicorn with a threaded worker.
SSE requires threading — a single worker keeps the subscriber list consistent across connections:

```
gunicorn -k gthread --workers 1 --threads 16 harbor:app
```

Configuration is passed via environment variables.
A minimal systemd service file:

```ini
[Unit]
Description=Harbor service registry
After=network.target caddy.service

[Service]
User=harbor
Environment=HARBOR_BACKEND=caddy
Environment=HARBOR_BACKEND_URL=unix:///run/caddy/admin.socket
Environment=HARBOR_STATIC_DIR=/etc/harbor/routes.d
ExecStart=gunicorn -k gthread --workers 1 --threads 16 harbor:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
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

## Priority services

Ephemeral services can declare themselves as high priority.
Gangway displays priority cards first in the grid with a distinct visual treatment.
Useful for services that require immediate user action, such as a device flow login.

Set the flag at registration time:

```json
{
  "id": "device-login",
  "prefix": "/login",
  "kind": "proxy",
  "upstreams": ["127.0.0.1:8080"],
  "ttl": 300,
  "priority": true
}
```

Or in a `.route` file:

```yaml
id: device-login
name: Device Login
kind: proxy
prefix: /login
upstreams:
  - 127.0.0.1:8080
priority: true
```
## Envoy backend (experimental)

> The Envoy backend is a work in progress and has not been tested against a real Envoy instance.
> The structure is in place but the xDS configuration will require iteration.

Harbor supports Envoy as a second backend, primarily for gRPC services with JSON transcoding and BFF authentication.
The typical deployment has Caddy as the front door, delegating gRPC routes to Envoy:
```
Client → Caddy :80 → Envoy :10000 → gRPC Service :9090
```

Envoy is configured via file-based xDS — Harbor writes `/run/envoy/cds.yaml` and `/run/envoy/lds.yaml` atomically, and Envoy picks up changes via inotify without restarting.

A minimal Harbor config for this setup:
```yaml
static_dir: /etc/harbor/routes.d
host: 0.0.0.0
port: 8080

backends:
  caddy:
    kind: caddy
    url: unix:///run/caddy/admin.socket
    options:
      server-name: srv0
    delegate:
      grpc: envoy

  envoy:
    kind: envoy
    options:
      listener-port: 10000
      admin-port: 9901
```

A gRPC service route:
```yaml
id: myservice
name: My gRPC Service
kind: grpc
prefix: /api/myservice
upstreams:
  - 127.0.0.1:9090
transcoder:
  proto_descriptor: /etc/harbor/proto/myservice.pb
  services:
    - myservice.v1.MyService
bff:
  enabled: true
```

See `contrib/envoy-bootstrap.yaml` for the Envoy bootstrap configuration.

## Future: service widgets

> This section documents a design direction for future consideration.
> It is not implemented beyond the `priority` flag above.

Services could expose a `.well-known/gangway` endpoint returning a small JSON descriptor:

```json
{
  "name": "Grafana",
  "description": "Metrics and dashboards",
  "icon": "/logo.png",
  "color": "#F46800",
  "status": "/api/health",
  "widget": "/gangway-widget.html",
  "size": "large"
}
```

Gangway would fetch this descriptor and use it to enrich the service card.
The `widget` field would point to a small HTML fragment that Gangway embeds directly — the service owns the rendering entirely, Gangway just provides the frame.
The `size` hint (`small`, `medium`, `large`) would map to CSS grid spans.

This approach keeps Harbor itself free of widget configuration complexity — services declare their own presentation, Harbor just routes.

---



MIT