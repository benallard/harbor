# Sidecars

A sidecar is an infrastructure service that runs alongside application services and augments them with additional capabilities.
Sidecars are never exposed via the ingress and never appear in the Gangway catalog.
They exist purely as backend resources that other services can reference by name.

---

## Concept

Some services require capabilities that go beyond simple proxying — external authorization, gRPC transcoding, rate limiting.
Rather than embedding these concerns in the service definition or the Harbor config, Harbor uses sidecars to express them.

A sidecar declares what it provides via `abilities`.
A service declares which sidecars it needs via `sidecars`.
Harbor's dispatcher finds the backend that handles each ability and wires them together automatically.

This keeps service definitions backend-agnostic.
A service says "I need authorization" — not "configure Envoy's ext_authz filter for me".

---

## Defining a sidecar

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
| `id` | yes | Unique identifier, referenced by services |
| `kind` | yes | Must be `sidecar` |
| `abilities` | yes | List of capabilities this sidecar provides |
| `upstreams` | yes | List of upstream addresses (`host:port`) |
| `name` | no | Human-friendly display name |

---

## Using a sidecar

A service references its sidecars by ID:

```yaml
id: myapi
name: My API
kind: proxy
prefix: /api
upstreams:
  - 127.0.0.1:8080
sidecars:
  - my-bff
```

When Harbor registers `myapi`, it:

1. Looks up the sidecars referenced by `myapi` — in this case `my-bff`
2. Collects their abilities — `authz`
3. Finds the backend that declares `authz` in its `features` — Envoy
4. Sends Caddy a plain proxy route pointing at Envoy's listener
5. Sends Envoy the full service definition, which it uses to activate the authz filter

---

## Known abilities

| Ability | Description | Typically handled by |
|---|---|---|
| `authz` | External authorization — session cookie to access token exchange | Envoy (`ext_authz` filter) |
| `transcoder` | gRPC-JSON transcoding | Envoy (`grpc_json_transcoder` filter) |
| `ratelimit` | Rate limiting | Envoy (ratelimit service) |
| `waf` | Web application firewall | Future |
| `cache` | Response caching | Future |

Ability names are Harbor's vocabulary, not backend-specific terms.
The backend maps each ability to its own internal implementation.

---

## BFF pattern

The BFF (Backend For Frontend) pattern involves two sides:

**HTTP side** — handles user login and issues session cookies.
This is a plain `kind=proxy` service with a prefix, served via the ingress like any other service:

```yaml
id: bff-login
name: BFF Login
kind: proxy
prefix: /auth
upstreams:
  - 127.0.0.1:8090
```

**gRPC side** — exchanges session cookies for access tokens on behalf of Envoy.
This is a `kind=sidecar` with `abilities: [authz]`:

```yaml
id: bff-authz
name: BFF Authorization
kind: sidecar
abilities:
  - authz
upstreams:
  - 127.0.0.1:9091
```

Services that require authentication reference the sidecar:

```yaml
id: myapi
kind: proxy
prefix: /api
upstreams:
  - 127.0.0.1:8080
sidecars:
  - bff-authz
```

---

## Multiple sidecars

A service can reference multiple sidecars:

```yaml
id: myapi
kind: proxy
prefix: /api
upstreams:
  - 127.0.0.1:8080
sidecars:
  - bff-authz
  - my-ratelimiter
```

Harbor collects all required abilities and finds the appropriate backend for each.

---

## Hot reload

Sidecar `.route` files are watched like any other route file.
Adding, modifying or deleting a sidecar takes effect immediately.
Backends that handle the sidecar's abilities are notified automatically.