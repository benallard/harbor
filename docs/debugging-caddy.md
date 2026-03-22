# Debugging Caddy

## Check live config
```bash
curl --unix-socket /run/caddy/admin.socket http://caddy/config/
```

Inspect a specific route by `@id`:
```bash
curl --unix-socket /run/caddy/admin.socket http://caddy/id/static-myservice
```

## Enable debug logging

Add to `/etc/caddy/Caddyfile`:
```caddyfile
{
    debug
}
```

## Common errors

- `409 Conflict` — route `@id` already exists, Harbor tried to `POST` instead of `PATCH`
- `404` on `/id/...` — route not registered, check Harbor logs for registration errors
- File server 403 — Caddy can't read the directory, check permissions and `PrivateTmp` in systemd
- SSE not streaming — check `X-Accel-Buffering: no` header is reaching the client