# Backends

Harbor supports multiple proxy backends.
Backends are configured in `harbor.yaml` and identified by name.
One backend is designated as the ingress — it receives all service events.
Other backends receive only what is delegated to them via sidecar abilities.

---

## Features

Backends declare capabilities they provide via the `features` list.
Services declare what they need via sidecars with matching abilities.
Harbor's dispatcher matches service requirements to backend capabilities automatically.

This keeps service definitions backend-agnostic — a service declares what it needs, not which backend provides it.
Swapping backends never requires changing service definitions.

Known feature names:

| Feature | Description |
|---|---|
| `authz` | External authorization filter (e.g. BFF session exchange) |
| `transcoder` | gRPC-JSON transcoding |
| `ratelimit` | Rate limiting |
| `waf` | Web application firewall |
| `cache` | Response caching |

Feature names are Harbor's vocabulary, not backend-specific terms.
Each backend maps them to its own internal implementation.

---

## Caddy

The recommended production backend.
Harbor configures Caddy via its Admin API over a unix socket.

```yaml
backends:
  caddy:
    kind: caddy
    url: unix:///run/caddy/admin.socket
    options:
      server-name: srv0    # name of the Caddy server block (default: srv0)
      listener-port: 80    # port Caddy listens on (default: 80)
```

### Caddyfile

Harbor expects Caddy to be running with the admin API enabled.
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
Harbor's service routes are more specific and always take priority.

Harbor's process user needs access to the socket:

```bash
sudo usermod -aG caddy <harbor-user>
```

### Behavior

- Routes are inserted at position 0 in the Caddy routes array, before the catch-all
- Each route is tagged with an `@id` for targeted updates and deletions
- Static services use the prefix `static-<id>`, ephemeral services use `ephemeral-<id>`
- Path prefix is stripped before forwarding when `strip_prefix: true` (default)
- When a service is delegated to another backend (e.g. Envoy), `strip_prefix` is automatically set to `false` — the delegate needs the full path
- When `protocol: http2` is set, Caddy uses HTTP/2 cleartext (`h2c`) transport for the upstream connection
- Standard forwarding headers are set: `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Prefix`, `X-Real-IP`, `Host`, `Forwarded`

---

## Envoy

> The Envoy backend is experimental and has not been tested against a real Envoy instance.

Used for services requiring gRPC-JSON transcoding or external authorization.
Typically deployed behind Caddy, which acts as the ingress.

```yaml
backends:
  envoy:
    kind: envoy
    options:
      listener-port: 10000   # port Envoy listens on (default: 10000)
      admin-port: 9901       # Envoy admin API port (default: 9901)
    features:
      - authz
      - transcoder
```

### Configuration model

Envoy is configured via file-based xDS.
Harbor writes `/run/envoy/cds.yaml` (clusters) and `/run/envoy/lds.yaml` (listeners and routes) atomically.
Envoy picks up changes via inotify without restarting.

### Bootstrap

Envoy must be started with a bootstrap config that watches Harbor's xDS files.
See `contrib/envoy-bootstrap.yaml`.

### Behavior

- Each service becomes a cluster in `cds.yaml`
- Each service route is added to the listener's route config in `lds.yaml`
- Services with `protocol: http2` get HTTP/2 cluster config (`http2_protocol_options`)
- Services with `transcoder` get per-route `grpc_json_transcoder` filter config
- Sidecars with `authz` ability become dedicated clusters wired to Envoy's `ext_authz` filter
- Routes are matched on the full path including prefix — Caddy does not strip the prefix when delegating
- All writes are atomic (`rename` after writing to a temp file)

---

## Flask

Development-only backend.
Harbor acts as the proxy itself — no external proxy required.

```yaml
backends:
  flask:
    kind: flask
    options:
      listener-port: 8080   # must match Harbor's own port
```

### Behavior

- Routes are matched by longest prefix first
- Path prefix is stripped before forwarding
- Standard forwarding headers are set
- Static file serving via Flask's `send_from_directory`
- No support for features or sidecar delegation

Not suitable for production — use Caddy instead.

---

## Multi-backend setup

The typical production setup with Caddy as ingress and Envoy for gRPC services:

```yaml
ingress: caddy

backends:
  caddy:
    kind: caddy
    url: unix:///run/caddy/admin.socket
    options:
      server-name: srv0

  envoy:
    kind: envoy
    options:
      listener-port: 10000
    features:
      - authz
      - transcoder
```

Traffic flow:

```
Client → Caddy :80 → Service (plain proxy/static)
                   → Envoy :10000 → gRPC Service (transcoding + authz)
```

Harbor's dispatcher routes service events to the right backend automatically based on sidecar abilities.
Caddy receives a plain proxy route pointing at Envoy's listener for services that require delegation.
Envoy receives the full service definition including transcoder and sidecar config.

See [Sidecars](sidecars.md) for how services declare their requirements.