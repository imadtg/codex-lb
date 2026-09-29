# Diagnose live SQLite and replay stalls

## Why
On 2026-09-28 the Redarchy proxy emitted widespread SQLite lock failures without naming a holder, and declined six full-resend handoffs for prefix fingerprint mismatches without enough evidence to explain the divergence. Existing post-transaction diagnostics cannot identify an ongoing stall. WebSocket disconnects and network recovery also require separation from local persistence failures.

## What Changes
Add bounded, content-free diagnostic summaries for these unresolved incidents where existing evidence is insufficient. Preserve routing, context, settlement and retention policy. Record the investigation and feasible isolated regression evidence.

## Scope
No live database edits, credentials, full payload tracing, account state changes or service restart during investigation.
