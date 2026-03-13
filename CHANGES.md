# Changelog

All notable changes to Harbor will be documented in this file.

## [Unreleased]

### Harbor
- Added `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Prefix`, `X-Real-IP`, `Host` and `Forwarded` (RFC 7239) headers to proxied requests
- Applied consistently to both Caddy and Flask backends
- Environment variable support for all configuration options (`HARBOR_BACKEND`, `HARBOR_BACKEND_URL`, `HARBOR_BACKEND_OPTIONS`, `HARBOR_STATIC_DIR`, `HARBOR_HOST`, `HARBOR_PORT`)
- `create_app()` now callable without arguments, reads from environment — enables `harbor:app` as a Gunicorn entrypoint
- SSE stream uses a 5 second queue timeout for clean Gunicorn shutdown and keepalive heartbeat
- Hot-reload of static routes — changes to `.route` files in `routes.d/` are picked up automatically without restarting Harbor
- `load_service` extracted from `load_services` for single-file loading
- `Registry.add_static` and `Registry.remove_static` for runtime static service management

## [0.10.0] - 2026-03-08

### Gangway
- Renamed from Bridge to Gangway throughout
- Removed Google Fonts dependency
- Removed header, added discreet fixed footer with attribution
- SSE status indicator moved to fixed top-right corner
- Harbor offline state with explanation message
- Catalog reload on SSE reconnect
- Priority service support — high-priority cards appear first with visual emphasis
- Priority card removal bug fixed
- Priority animation conflict with disappear animation fixed

### Harbor
- `priority` flag added to `Service` model, registration API and catalog
- Widget future direction documented in README

## [0.9.0] - 2026-03-08

Initial release.

### Core

- Service registry with static and ephemeral service support
- TTL-based leases for ephemeral services with automatic renewal
- Background GC thread to remove expired services
- Observable registry pattern — backend and catalog react to registry events via subscriptions

### Proxy backends

- Caddy backend via Admin API over unix socket
- Flask embedded proxy backend for development
- Pluggable backend architecture for future Traefik, nginx support

### API

- `POST /services` — register an ephemeral service
- `DELETE /services/<id>` — unregister a service
- `POST /services/<id>/renew` — renew a lease
- `GET /catalog` — list all public services
- `GET /catalog/icon/<id>` — retrieve a service icon
- `GET /catalog/stream` — SSE stream of live catalog updates (`registered`, `unregistered`, `expired`)

### Gangway

- Minimal SPA dashboard displaying public services in real time
- Light/dark theme following system preference
- Live updates via SSE — cards appear and disappear without polling
- Adaptive gangway watermark illustration

### Configuration

- `.route` files in `/etc/harbor/routes.d/` for static service declaration
- CLI arguments for backend, socket path, bind address and port
- `public: false` flag to hide services from the catalog

### Tests

- Unit tests for registry, Caddy backend, API blueprints and Flask proxy router