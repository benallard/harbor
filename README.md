# Harbor

Managing a reverse proxy on a single host is straightforward — until services start coming and going.
You add a route for a new service, restart the proxy, maybe break something else.
You spin up a preview environment, forget to clean up, end up with stale routes.
You want to expose a gRPC service over HTTP/JSON, and suddenly you're deep in Envoy documentation.

Harbor solves this by sitting alongside your proxy and managing its configuration for you.
You describe your services in simple `.route` files.
Harbor registers them with the proxy at startup, watches for changes, and updates routes on the fly — no restarts, no manual edits.
When a service is ephemeral, it registers itself with a TTL lease and Harbor cleans it up automatically when the lease expires.

---

## What problem does it solve?

### Static configuration drift

On a typical single-host setup, proxy config lives in a file that grows organically.
Routes get added, old ones linger, nobody remembers what `/legacy-api` points to.
Harbor replaces this with a directory of `.route` files — one per service, declarative, version-controllable, hot-reloaded.

### Ephemeral services

Some services are transient — a preview environment, a device flow login, a one-off job.
They need a clean URL but not a permanent route.
With Harbor, they register themselves via API with a TTL lease, get a route, and disappear cleanly when done.
No cleanup scripts, no stale config.

### Multi-backend orchestration

A gRPC service exposed over HTTP/JSON needs Envoy for transcoding and authentication.
But it also needs Caddy to route traffic to Envoy.
Harbor coordinates both: one service definition, Harbor tells each backend exactly what it needs to know.

---

## Why Harbor over alternatives?

| | Harbor | Manual proxy config | Kubernetes Ingress | Traefik |
|---|---|---|---|---|
| Single-host focus | ✅ | ✅ | ❌ | ✅ |
| No container requirement | ✅ | ✅ | ❌ | ⚠️ |
| Ephemeral services with TTL | ✅ | ❌ | ❌ | ⚠️ |
| Multi-backend (Caddy + Envoy) | ✅ | ❌ | ❌ | ❌ |
| Hot reload without restart | ✅ | ⚠️ | ✅ | ✅ |
| gRPC transcoding + authz | ✅ | ❌ | ⚠️ | ⚠️ |
| Live dashboard (Gangway) | ✅ | ❌ | ⚠️ | ✅ |

Harbor is not a replacement for Kubernetes or a full service mesh.
It is for developers and operators who run services directly on a Linux host and want the same dynamic routing experience without the infrastructure overhead.

---

## How it works

Harbor sits alongside your proxy and manages its configuration via API.
It never handles traffic itself in production — it just tells the proxy what to route where.

```
Client → Caddy → Service
            ↑
          Harbor
```

**Static services** are declared in `.route` files in `/etc/harbor/routes.d/`.
Harbor registers them with the proxy at startup and watches the directory for changes.
Add, modify or delete a `.route` file — Harbor picks it up immediately.

**Ephemeral services** register themselves via Harbor's internal API with a TTL lease.
Harbor adds the route, and removes it automatically when the lease expires or is not renewed.

**Sidecars** are infrastructure services — an auth filter, a rate limiter, a transcoder.
A service declares which sidecars it needs; Harbor wires them to the right backend automatically.

A companion SPA — **Gangway** — displays all public services in real time, served directly by Caddy so it stays available even when Harbor is down.

---

## Quick start

```bash
poetry install
poetry run harbor
```

Define a service in `/etc/harbor/routes.d/grafana.route`:

```yaml
id: grafana
name: Grafana
kind: proxy
prefix: /grafana
upstreams:
  - 127.0.0.1:3000
```

Harbor registers the route with Caddy immediately.
Visit `http://localhost/grafana` — done.

Register an ephemeral service:

```bash
curl -X POST http://localhost:8080/services \
  -H "Content-Type: application/json" \
  -d '{"id": "preview", "prefix": "/preview", "kind": "proxy", "upstreams": ["127.0.0.1:9000"], "ttl": 300}'
```

The route appears in Caddy, shows up in Gangway, and disappears automatically after 5 minutes.

---

## Documentation

Full documentation is available in [docs/](docs/):

- [Routes](docs/routes.md) — `.route` file format, all kinds and fields
- [Configuration](docs/configuration.md) — `harbor.yaml`, env vars, CLI args, ephemeral API
- [Backends](docs/backends.md) — Caddy, Envoy, Flask, features and delegation
- [Sidecars](docs/sidecars.md) — authz, transcoding, and the sidecar pattern
- [Gangway](docs/gangway.md) — the live dashboard, catalog API, SSE
- [Debugging Caddy](docs/debugging-caddy.md)
- [Debugging Envoy](docs/debugging-envoy.md)

---

## Project structure

```
harbor/
  api/        REST API (services, catalog)
  core/       registry, dispatcher, models, GC
  backend/    Caddy, Envoy, Flask backends
  tasks/      GC and filesystem watcher
gangway/      live dashboard SPA
contrib/      Caddyfile, systemd service, Envoy bootstrap
docs/         documentation
tests/
```

---

## License

MIT