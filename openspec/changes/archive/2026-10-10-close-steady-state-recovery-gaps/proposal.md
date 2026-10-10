## Why

The fork preserves projectable context but still cancels terminal SQLite writes at a short delivery bound, misses message-only usage exhaustion, and needs writer-slot readiness and route-level recovery coverage. Recorded compatibility tests cover the fork base rather than independent official builds.

## What Changes

- Retain the scoped #2555 terminal-append fix and port #2449 message-shaped quota recognition.
- Detect sustained SQLite writer-slot loss with a bounded independent acquisition probe and readiness failure, without adding settings or schema.
- Reconcile #2581/#2398 reconnect proof and health ordering with the fork's context retention policy; preserve pending-tool and execution fences.
- Apply the confirmed #2472 lease closure repair independently of disputed transport relabeling.
- Verify runtime contention and ordinary state interchange with independently fingerprinted official upstream builds before deployment.

## Impact

Affected capabilities: database-backends, responses-api-compat, account-routing, usage-refresh-policy, proxy-runtime-observability. No client changes, new configuration, schema migration, thread conversion, or model-source portability expansion.
