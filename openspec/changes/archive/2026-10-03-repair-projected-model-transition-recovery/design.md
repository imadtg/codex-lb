## Context

See proposal.md for the incident motivation. The HTTP bridge separates portable history proof, durable operation ownership, and isolated transport sessions. The failures arose when these layers disagreed after a model transition.

## Goals

Reuse the existing projection and execution fences. Preserve useful instructions and the supported reasoning/compaction projection without adding configuration or a database migration.

## Decisions

### Validate every instruction in the developer block

Extend the existing settled-final-answer boundary check to accept consecutive developer messages through the same plaintext validator. The following user message is still required. File references, opaque content, unfinished tool batches, and assistant commentary do not become portable merely because they occur in a block. Removing the instructions would discard useful context and is unnecessary.

### Fence turn-token requests before dispatch

Register durable operations for hard continuity anchors even when previous_response_id is absent. Detect explicit quota rejection from the upstream error rather than a helper that requires that optional response id. Eligible requests reach the existing outer fenced recovery path before an inner retry consumes their replay allowance. The outer path still requires complete context proof, no visible or accepted output, no file owner, and exclusive operation ownership.

### Publish the completed logical generation in the existing alias table

Record a scoped logical_thread alias in the same owner-fenced transaction that publishes the completed response and its history proof. Failed response publication cannot advance the hint. Resolve explicit turn/response/session aliases first, then the logical generation hint, then the canonical-key fallback. The hint uses the existing process/thread identity and API-key scope. Earlier response and turn aliases continue to identify their original sessions.

A canonical row alone cannot name the compacted model fork after its socket closes. Reusing the alias table avoids a schema change and keeps the generation hint atomic with existing completion persistence. Concurrent generations follow completion publication order; explicit anchors retain their exact meaning and portable history still has to match the selected proof.

### Distinguish ordinary forks from active recovery attempts

An ordinary internal_unanchored_parallel fork may yield its token after verified projection. A live account-neutral-replay:v1: fork still serializes replacement attempts. The SQL conflict predicate excludes that namespace from ordinary rebind eligibility. Rejected replacement publication restores predecessor aliases; accepted or ambiguous dispatch retains its existing execution protection.

## Verification approach

Three public-process regressions drive the real service through HTTP account import/settings/pause and a synthetic WebSocket upstream. They assert completed output, alternate-account selection, the entire projected input, removal of old upstream affinity, and a successful following request. Application imports, monkeypatches, and database writes are not used by the probe.

Focused repository tests check scoped generation resolution, explicit old anchors, failed publication, ordinary fork rebinding, and competition between live recovery lanes. Existing public controls cover missing tool outputs, accepted/visible output, ambiguous replacement, and reasoning/agent-message projection.

The replacement controls explicitly pause the original owner through the public API before returning its missing-response error. Otherwise that still-eligible owner can legitimately be selected again, making the previous fixtures nondeterministic. The corrected controls pass on both baseline and patched source.

## Compatibility and rollout

This is a local patch against f9c2cb51; deployment is separate. Existing databases need no migration. New hints are written on successful completion, and missing hints retain the previous lookup behavior. Existing explicit turn/response aliases can still recover portable history through the repaired quota path. Historical forks do not contain a reversible logical-thread identity in their hashed keys, so this change does not invent a backfill association or recreate deleted history proofs. A legacy fork without a recorded hint or matching explicit anchor may still require client context recovery before its first completion on the new build.

Rollback can use the previous executable against the same schema. It ignores the new alias kind and retains its earlier recovery limitations.

The process tests verify wire projection and routing; they do not establish how a live model interprets lossy context.
