## Why

The transcript flusher wakes and writes on every enqueue. A paced stream can
therefore commit one event per transaction despite a configured accumulation
interval. Historical small-write pressure and terminal persistence timeouts
justify reducing these writes without changing completion or replay contracts.

## What Changes

- Schedule each operation from its oldest pending event's monotonic timestamp.
- Flush at the existing interval or batch-size threshold; drains bypass delay.
- Export bounded batch outcome, size, bytes, queue age and write-duration metrics.
- Verify paced public streaming, completion, interruptions and base/fork replay.
- Evaluate the existing chunk writer without changing its default or schema.

## Capabilities

### New Capabilities

### Modified Capabilities

- `responses-api-compat`: enforce accumulation scheduling and bounded diagnostics.

## Impact

The existing batcher and optional Prometheus surface change. Existing settings,
database schema, SSE events, ownership fences and incomplete-spool rules remain
the compatibility contract. Checkpoint policy and retention require separate
measured justification.
