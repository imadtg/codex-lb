# Bound hard-owner recovery

## Why
The September 13 deployment exposed repeated hard-affinity selection waits after
HTTP fallback. A recent WebSocket failure is a process-local 60-second marker,
not evidence of a persisted restart or an unrecoverable request. The rushed
dc715582 condition therefore has no valid restart-specific justification.

## What Changes
- Reproduce hard-owner waits using public account and Responses APIs.
- Test both persistent unavailability and recovery within the short wait.
- Replace transport-marker-dependent behavior with a bounded selection recovery
  window if the public reproducer confirms the wait is unbounded.
- Validate in an isolated checkout before any deployment.
- Permit account-neutral replay when an exact persisted tool manifest is
  settled despite ordinary retained assistant commentary immediately before it.

## Impact
HTTP streaming selection and replay classification only; no schema changes or
production data experiments.
