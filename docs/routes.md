# Routes

Routes are declared as `.route` files in `/etc/harbor/routes.d/`.
Each file describes one service or sidecar.
Harbor watches this directory for changes and picks them up automatically without restarting.

---

## Kinds

Harbor supports three route kinds:

- `proxy` — reverse proxies requests to one or more upstreams
- `static` — serves files from a local directory
- `sidecar` — infrastructure service used by other services, never exposed via the ingress

---

## Common fields

These fields apply to all kinds:

| Field | Required | Description |
|---|---|---|
| `id` | yes | Unique identifier |
| `kind` | yes | `proxy`, `static`, or `sidecar` |
| `name` | no | Human-friendly display name |
| `source` | no | Set automatically by Harbor (`file` or `dynamic`) |

---

## Proxy routes

Reverse proxies requests to one or more upstreams.
The request path prefix is stripped before forwarding.
Standard forwarding headers are set automatically (`X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Prefix`, `X-Real-IP`, `Host`, `Forwarded`).

```yaml
id: grafana
name: Grafana
kind: proxy
prefix: /grafana
upstreams:
  - 127.0.0.1:3000
icon: /assets/grafana.png
```

| Field | Required | Description |
|---|---|---|
| `prefix` | yes | Path prefix to match |
| `upstreams` | yes | List of upstream addresses (`host:port`) |
| `public_paths` | no | Restrict proxying to specific sub-paths (relative to prefix) |
| `public` | no | Whether to include in the Gangway catalog (default: `true`) |
| `priority` | no | Display this service prominently in Gangway (default: `false`) |
| `icon` | no | URL or path to a service icon |
| `sidecars` | no | List of sidecar IDs required by this service |
| `transcoder` | no | gRPC-JSON transcoding config (see below) |

### Restricting public paths

Use `public_paths` to only expose specific sub-paths of a service.
Paths are relative to the prefix.

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
```

### gRPC transcoding

Services that require gRPC-JSON transcoding declare a `transcoder` block.
This requires an Envoy backend with the `transcoder` feature.

```yaml
id: myservice
name: My gRPC Service
kind: proxy
prefix: /api/myservice
upstreams:
  - 127.0.0.1:9090
transcoder:
  proto_descriptor: /etc/harbor/proto/myservice.pb
  services:
    - myservice.v1.MyService
```

---

## Static routes

Serves files from a local directory.
The request path prefix is stripped before resolving the file path.

```yaml
id: docs
name: Documentation
kind: static
prefix: /docs
directory: /srv/docs
```

| Field | Required | Description |
|---|---|---|
| `prefix` | yes | Path prefix to match |
| `directory` | yes | Absolute path to the directory to serve |
| `public` | no | Whether to include in the Gangway catalog (default: `true`) |
| `icon` | no | URL or path to a service icon |

The served directory must be readable by the proxy process (e.g. the `caddy` user).
Avoid serving from `/tmp` — systemd's `PrivateTmp` makes it invisible to other processes.
Prefer `/srv/harbor/<service>/` or `/var/www/<service>/`.

---

## Sidecar routes

Infrastructure services used by other services.
Sidecars are never exposed via the ingress and never appear in the Gangway catalog.
They are registered directly with the backend that handles their abilities.

```yaml
id: my-bff
name: BFF Authentication
kind: sidecar
abilities:
  - authz
upstreams:
  - 127.0.0.1:9091
```

| Field | Required | Description |
|---|---|---|
| `upstreams` | yes | List of upstream addresses (`host:port`) |
| `abilities` | yes | List of capabilities this sidecar provides |
| `name` | no | Human-friendly display name |

A service references its sidecars by ID:

```yaml
id: myapi
kind: proxy
prefix: /api
upstreams:
  - 127.0.0.1:8080
sidecars:
  - my-bff
```

Harbor finds the backend that handles each sidecar's abilities and wires them together automatically.
See [Sidecars](sidecars.md) for the full picture.

---

## Ephemeral services

Services can also be registered dynamically via Harbor's internal API with a TTL lease.
See [Configuration](configuration.md) for the API reference.

---

## File naming

The filename has no effect on routing — only the `id` field matters.
Use descriptive names for clarity:

```
/etc/harbor/routes.d/
  grafana.route
  docs.route
  my-bff.route
```

---

## Hot reload

Harbor watches `/etc/harbor/routes.d/` for changes via filesystem events.
Adding, modifying or deleting a `.route` file takes effect immediately.
No restart needed.