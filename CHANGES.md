# Changelog

All notable changes to Harbor will be documented in this file.

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