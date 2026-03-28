# AGENTS.md

## Setup

```bash
poetry install
poetry run harbor                  # start with default config
poetry run harbor --backend flask  # development mode, no Caddy needed
poetry run pytest                  # run tests
poetry run black .                 # format
poetry run ruff check .            # lint
```

---

## Architecture overview

Harbor is a service registry and proxy controller.
It does not handle traffic — it tells proxies what to route where.
The core loop is: registry emits events → dispatcher routes them → backends configure proxies.

```
.route files → Registry → Dispatcher → Backends (Caddy, Envoy, ...)
API calls   ↗                        → Catalog (SSE → Gangway)
```

---

## Key design decisions

### Observable registry
The registry emits `registered`, `unregistered`, and `expired` events.
Backends and the catalog subscribe to these events rather than being called directly.
This keeps `create_app` as pure dependency injection with no logic.
The dispatcher is subscribed as a single entry point — it fans out to backends.

### Dispatcher owns delegation
The dispatcher is the only place that knows about backend delegation.
Backends are completely unaware of each other.
When a service requires a sidecar capability, the dispatcher:
1. Transforms the service into a plain proxy route pointing at the delegate's listener
2. Sends the transformed service to the ingress backend (e.g. Caddy)
3. Sends the original service to the delegate backend (e.g. Envoy)

### One ingress
Only one backend sits in the front row (`ingress` in `harbor.yaml`).
All service events go to the ingress first.
Other backends only receive what is delegated via sidecar abilities.
This avoids ambiguity about who configures what.

### Feature/ability vocabulary is backend-agnostic
Feature names (`authz`, `transcoder`, `ratelimit`) are Harbor's vocabulary, not backend terms.
Backends map them to their own internal implementations (e.g. `authz` → Envoy's `ext_authz`).
Service definitions never reference backend-specific terms.
This allows swapping backends without changing service definitions.

### Sidecars are services with `kind=sidecar`
Sidecars are not a separate dataclass — they are `Service` objects with `kind=sidecar`.
They have no prefix, no catalog entry, no ingress route.
They declare `abilities` that backends match against their `features`.
Services reference sidecars by ID via the `sidecars` list field.
The dispatcher looks up sidecars from the registry to determine delegation.

### `kind=grpc` was deliberately removed
gRPC is just HTTP/2 proxying — `kind=proxy` covers it.
The presence of a `transcoder` field signals that transcoding is needed.
Adding a `kind=grpc` would have been redundant and backend-specific.

### File-based xDS for Envoy
We chose file-based xDS over a gRPC control plane for simplicity.
Envoy watches `/run/envoy/cds.yaml` and `/run/envoy/lds.yaml` via inotify.
Harbor writes these files atomically using `os.rename()` after writing to a temp file.
This gives true dynamic config without implementing the xDS gRPC streaming protocol.
Delta xDS would be more efficient but adds significant complexity — deferred.

### Caddy admin API over unix socket
The admin socket path is `unix:///run/caddy/admin.socket` by default.
Socket permissions must be `0660` with the Caddy group — set via `|0660` in the Caddyfile.
Routes are inserted at index 0 (not appended) so they take priority over the catch-all.
Each route carries an `@id` tag (`static-<id>` or `ephemeral-<id>`) for targeted updates.
Upsert logic: `GET /id/<route-id>` → 404 means `POST`, 200 means `PATCH`.

### `harbor.wsgi:app` as Gunicorn entry point
`harbor/__init__.py` exposes `app = create_app()` which conflicts with `harbor/app.py` module.
`harbor/wsgi.py` is the dedicated Gunicorn entry point to avoid this naming conflict.
`create_app()` called without arguments reads from environment variables via `default_config()`.

### SSE keepalive and clean shutdown
The SSE stream uses `q.get(timeout=5)` rather than blocking indefinitely.
On timeout, a `: keepalive` comment is sent to keep the connection alive through proxies.
This also allows Gunicorn to shut down cleanly without waiting forever for SSE threads.
Run with `gunicorn -k gthread --workers 1 --threads 16 harbor.wsgi:app`.
Single worker is required — multiple workers would have separate in-process subscriber lists.

### Static file serving location
Avoid serving static files from `/tmp` — systemd's `PrivateTmp=true` makes it invisible to Caddy.
Use `/srv/harbor/<service>/` or `/var/www/<service>/` instead.

### Gangway served by Caddy directly
Gangway (the SPA) is served by Caddy as a static catch-all, not by Harbor.
This means Gangway remains available even when Harbor is down.
When Harbor is unreachable, Gangway displays an explanation rather than an empty page.
When Harbor comes back, Gangway reconnects via SSE and repopulates automatically.

### `.route` files, not `.yaml` or `.service`
Route files use the `.route` extension and live in `routes.d/` (not `services.d/` or `service.d/`).
The filename has no effect on routing — only the `id` field matters.
The watcher picks up `.route` files via filesystem events — no restart needed.

### Configuration precedence
CLI args > environment variables > config file > defaults.
`harbor.yaml` is the recommended approach for multi-backend production deployments.
Env vars (`HARBOR_BACKEND`, `HARBOR_BACKEND_URL`, etc.) cover simple single-backend setups.
`argparse` defaults are set from env vars so both paths share the same defaults.

---

## Code conventions

- One sentence per line in documentation and commit messages
- `%s` style in logging, never f-strings (lazy evaluation)
- Relative imports within the `harbor` package
- Backend-specific config in dedicated dataclasses (`CaddyConfig`, `EnvoyConfig`, `FlaskConfig`)
- `factory.py` is a dict mapping kind strings to backend classes — add new backends there
- Tests use `MagicMock` for backends, `pytest-httpx` for HTTP assertions in `test_caddy.py`
- `conftest.py` provides `app`, `client`, `mock_backend`, `flask_app`, `flask_client` fixtures

---

## Adding a new backend

1. Create `harbor/backend/<name>.py` with a class extending `ProxyBackend`
2. Implement `apply`, `register`, `unregister`, `on_event`, `listener_url`
3. Add a config dataclass `<Name>Config` with `from_backend_config` factory
4. Register the class in `harbor/backend/factory.py` BACKENDS dict
5. Declare supported `features` in `harbor.yaml` under the backend entry
6. Add tests in `tests/test_<name>.py` using `pytest-httpx` or appropriate mocks

---

## Adding a new sidecar ability

- Sidecars arrive via `on_event` with `service.kind == "sidecar"` — backends check the kind and handle accordingly
- The base class `on_event` default is a no-op, so backends that don't handle sidecars need no changes

---

## Project layout

```
harbor/
  api/
    services.py    internal API (register/unregister/renew)
    catalog.py     public API (catalog, SSE stream)
  core/
    models.py      Service, Lease dataclasses
    registry.py    observable registry
    dispatcher.py  event routing and backend delegation
    config.py      HarborConfig, BackendConfig, load_config
    loader.py      load .route files
    gc.py          TTL expiry background thread
  backend/
    base.py        ProxyBackend abstract base class
    caddy.py       Caddy Admin API backend
    envoy.py       Envoy xDS file-based backend (experimental)
    flask_proxy.py embedded Flask proxy backend
    factory.py     backend registry dict
  tasks/
    gc.py          GC thread factory
    watcher.py     filesystem watcher for routes.d
  wsgi.py          Gunicorn entry point
  app.py           create_app, main, parse_args
gangway/
  index.html       Gangway SPA (placeholder, production SPA built separately)
contrib/
  Caddyfile        reference Caddy configuration
  envoy-bootstrap.yaml  reference Envoy bootstrap
  harbor.service   systemd service file
docs/
  index.md
  routes.md
  configuration.md
  backends.md
  sidecars.md
  gangway.md
  debugging-caddy.md
  debugging-envoy.md
tests/
  conftest.py
  fixtures/routes.d/   static .route files for testing
  test_registry.py
  test_caddy.py
  test_dispatcher.py
  test_api.py
  test_flask_proxy.py
```