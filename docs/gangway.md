# Gangway

Gangway is Harbor's companion SPA dashboard.
It displays all public services in real time, updating automatically as services come and go via SSE.
It is served directly by Caddy as a static site, so it remains available even when Harbor is not running.

---

## Catalog API

Gangway consumes Harbor's public catalog API.
These endpoints are served by Harbor and proxied through Caddy.

### List public services

```
GET /catalog
```

Returns all services where `public: true`.
Sidecar services are never included.

Example response:

```json
[
  {
    "id": "grafana",
    "name": "Grafana",
    "prefix": "/grafana",
    "icon": "/assets/grafana.png",
    "source": "file",
    "priority": false
  }
]
```

### Retrieve a service icon

```
GET /catalog/icon/<id>
```

Returns the icon URL or path for a given service.
Returns 404 if the service has no icon.

### Live updates via SSE

```
GET /catalog/stream
```

An SSE stream that emits events whenever services are registered, unregistered, or expire.

Event format:

```
data: {"event": "registered", "service": {...}}
data: {"event": "unregistered", "service": {...}}
data: {"event": "expired", "service": {...}}
```

Gangway subscribes to this stream on load and updates the dashboard in real time without polling.
A keepalive comment is sent every 5 seconds to keep the connection alive through proxies.

---

## Priority services

Services can declare themselves as high priority.
Gangway displays priority cards first in the grid with a distinct visual treatment — a colored border and a subtle pulsing animation.

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

Priority is particularly useful for ephemeral services that require immediate user action, such as a device flow login.

---

## Offline behavior

Since Gangway is served directly by Caddy, it loads even when Harbor is not running.
If the catalog API is unreachable, Gangway displays a message explaining that Harbor is not running.
When Harbor comes back up, Gangway reconnects automatically and repopulates the dashboard.

---

## Deployment

Gangway is a single static HTML file with no build step and no external dependencies.
Drop it in the directory Caddy serves as its catch-all:

```bash
sudo cp gangway/index.html /var/www/bridge/index.html
```

The Caddyfile catch-all serves it at `/`:

```caddyfile
:80 {
    try_files {path} /index.html
    file_server {
        root /var/www/bridge
    }
}
```

---

## Future: service widgets

> This section documents a design direction for future consideration.
> It is not currently implemented beyond the `priority` flag.

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
The `widget` field points to a small HTML fragment that Gangway embeds — the service owns the rendering entirely.
The `size` hint (`small`, `medium`, `large`) would map to CSS grid spans.

This approach keeps Harbor free of widget configuration complexity — services declare their own presentation, Harbor just routes.