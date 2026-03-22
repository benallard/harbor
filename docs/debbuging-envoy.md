# Debugging Envoy

## Check live config
```bash
curl http://localhost:9901/config_dump
```

Check clusters and their health:
```bash
curl http://localhost:9901/clusters
```

Check active listeners and routes:
```bash
curl http://localhost:9901/listeners
curl http://localhost:9901/routes
```

## Check xDS file reload

Envoy logs a message when it picks up a file change.
Check with:
```bash
journalctl -u envoy -f | grep -i "dynamic"
```

## Common errors

- Cluster not appearing — check `/run/envoy/cds.yaml` was written correctly, verify `@type` URLs are exact
- Routes not matching — check `/run/envoy/lds.yaml`, verify `prefix` matches the service prefix
- gRPC transcoding failing — verify `proto_descriptor` path is correct and readable by Envoy
- BFF filter rejected — check `ext_authz` cluster is healthy via `/clusters`
- xDS parse error — Envoy logs the exact field that failed, check `journalctl -u envoy`