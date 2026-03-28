# Harbor

Some services are always there — dependable, unmoving, like ships that never leave port.
Others come and go, appearing just long enough to do their job before disappearing again.
Harbor manages both.

Harbor is a lightweight service registry and proxy controller for single-host environments.
It registers routes with your reverse proxy at startup for static services, and adds or removes them on the fly as ephemeral services come and go.
When a lease expires, Harbor cleans up automatically.

A companion SPA — **Gangway** — provides a real-time dashboard of all public services, updated live via SSE.

---

## Quick start
```
poetry install
poetry run harbor
```

See the [documentation](docs/) for configuration, backends, route definitions, and deployment.

---

## How it works
```
Client → Caddy → Service
            ↑
          Harbor
```

Harbor sits alongside your reverse proxy and manages its routing configuration via API.
Static services are declared in `.route` files and registered at startup.
Ephemeral services register via Harbor's internal API with a TTL lease.

---

## Project structure
```
harbor/
  api/        REST API blueprints (services, catalog)
  core/       registry, leases, models, GC, dispatcher
  backend/    proxy backends (caddy, envoy, flask)
  tasks/      GC and filesystem watcher
gangway.html  Gangway SPA
contrib/      deployment files (Caddyfile, systemd, Envoy bootstrap)
docs/         documentation
tests/
```

---

## License

MIT