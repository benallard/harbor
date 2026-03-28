# Configuration

Harbor can be configured via a config file, environment variables, or CLI arguments.
The precedence order is: CLI arguments > environment variables > config file > defaults.

---

## Config file

The recommended approach for production deployments.
Pass the path via `--config` or `HARBOR_CONFIG`:

```
poetry run harbor --config /etc/harbor/harbor.yaml
```

### Schema

```yaml
static_dir: /etc/harbor/routes.d   # directory for .route files
host: 0.0.0.0                      # host to bind on
port: 8080                         # port to bind on
ingress: caddy                     # name of the front-row backend

backends:
  caddy:
    kind: caddy
    url: unix:///run/caddy/admin.socket
    options:
      server-name: srv0
      listener-port: 80

  envoy:
    kind: envoy
    options:
      listener-port: 10000
      admin-port: 9901
    features:
      - authz
      - transcoder
```

### `ingress`

Names the backend that sits in the front row and receives all service events.
All other backends only receive what is delegated to them via sidecar abilities.
Defaults to `default` when using env vars or CLI args (single backend mode).

### `backends`

A named map of backend configurations.
Order is preserved but not significant — backends are identified by name, not position.

Each backend entry supports:

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Backend type: `caddy`, `envoy`, or `flask` |
| `url` | no | Admin API URL or unix socket |
| `options` | no | Backend-specific key-value options |
| `features` | no | Capabilities this backend provides (e.g. `authz`, `transcoder`) |

---

## Environment variables

For simple single-backend deployments without a config file:

| Variable | Default | Description |
|---|---|---|
| `HARBOR_CONFIG` | — | Path to a harbor.yaml config file |
| `HARBOR_BACKEND` | `caddy` | Backend kind |
| `HARBOR_BACKEND_URL` | `unix:///run/caddy/admin.socket` | Backend admin URL |
| `HARBOR_BACKEND_OPTIONS` | — | Space-separated `key=value` backend options |
| `HARBOR_STATIC_DIR` | `/etc/harbor/routes.d` | Directory for `.route` files |
| `HARBOR_HOST` | `0.0.0.0` | Host to bind on |
| `HARBOR_PORT` | `8080` | Port to bind on |

---

## CLI arguments

All options are also available as CLI arguments:

```
poetry run harbor --help
```

| Argument | Description |
|---|---|
| `--config` | Path to harbor.yaml |
| `--backend` | Backend kind |
| `--backend-url` | Backend admin URL |
| `--backend-option` | Backend option (repeatable, `key=value`) |
| `--static-dir` | Directory for `.route` files |
| `--host` | Host to bind on |
| `--port` | Port to bind on |

---

## Ephemeral service API

The following endpoints are available on Harbor's internal API (default: `http://localhost:8080`).
These are intended for local services only and should not be exposed publicly.

**Register a service:**

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

**Renew a lease:**

```
POST /services/<id>/renew
Authorization: <lease-token>
```

**Unregister a service:**

```
DELETE /services/<id>
```

---

## Deployment

Harbor is designed to run under Gunicorn with a threaded worker.
SSE requires threading — a single worker keeps the subscriber list consistent across connections:

```
gunicorn -k gthread --workers 1 --threads 16 harbor.wsgi:app
```

A minimal systemd service file is available in `contrib/harbor.service`.
Configuration is passed via environment variables in the service file.