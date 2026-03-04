# Harbor

Harbor is a lightweight service registry and reverse proxy controller designed for single-host environments.

It dynamically exposes services under path prefixes and manages reverse proxy configuration for backends like **Caddy**.

Harbor supports both **static configuration** and **dynamic ephemeral services with TTL leases**.

---

## Features

- Dynamic service registration via REST API
- TTL-based leases to avoid stale routes
- Static configuration via `/etc/harbor/service.d`
- Pluggable proxy backends
- SPA dashboard support
- Optional embedded proxy for development

---

## Architecture

Typical deployment:

```
Client
↓
Caddy
↓
Service
```


Harbor manages proxy routes via the **Caddy Admin API**.

Alternative mode:

```
Client
↓
Harbor (Flask proxy backend)
↓
Service
```


---

## Service Model

A service is exposed under a **path prefix**.

Example:

```
/grafana → http://localhost:3000
```


Service types:

- proxy
- static

Example configuration:

```yaml
name: grafana
type: proxy
prefix: /grafana
upstreams:
  - http://127.0.0.1:3000
```

---

## Dynamic Services

Dynamic services are registered via API and expire unless renewed.

Register:

```
POST /services
```

Response:

```json
{
  "id": "preview-123",
  "lease": "secret-token",
  "ttl": 60
}
```

Renew lease:
```
POST /service/<id>/renew
Authorization: Bearer <lease-token>
```

If the lease expires, Harbor removes the route automatically.
---

## Configuration

Environment variables:
```
HARBOR_BACKEND=caddy
HARBOR_CADDY_ADMIN=http://127.0.0.1:2019
HARBOR_HOST=0.0.0.0
HARBOR_PORT=8080
```

Backends:
```
caddy
flask
```

Caddy is recommended for production.

## Installation

`poetry install`

Run Harbor:

`poetry run harbor`

Development Mode
Run Harbor with embedded proxy:

`HARBOR_BACKEND=flask poetry run harbor`

## Tests

Run tests with:

`poetry run pytest`

`poetry run black .`

`poetry run ruff check .`

## Project Structure

```
harbor/
  api/        REST API
  core/       service registry and leases
  proxy/      proxy backends
  render/     route rendering
tests/
```

## License
MIT
