# Harbor

Some services are always there — dependable, unmoving, like ships that never leave port.
Others come and go, appearing just long enough to do their job before disappearing again.
Harbor manages both.

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
Changes to `.route` files are picked up automatically via filesystem watching — no restart needed.

### Embedded proxy mode

For local development, Harbor can act as the proxy itself:

```
Client → Harbor → Service
```

No Caddy required.
Useful for testing without a full proxy setup.

---

## Quick start

```
poetry install
poetry run harbor
```

Harbor will look for `.route` files in `/etc/harbor/routes.d/` and register them with Caddy on startup.

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
poetry run harbor --backend flask
```

Deploy with Gunicorn:

```
gunicorn -k gthread --workers 1 --threads 16 harbor.wsgi:app
```

A systemd service file is available in `contrib/harbor.service`.

---

## Project structure

```
harbor/
  api/        REST API blueprints (services, catalog)
  core/       registry, leases, models, GC, dispatcher
  backend/    proxy backends (caddy, envoy, flask)
  tasks/      GC and filesystem watcher
gangway/      Gangway SPA
contrib/      deployment files (Caddyfile, systemd, Envoy bootstrap)
docs/         this documentation
tests/
```

---

## License

MIT