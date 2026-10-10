# Design: compatibility without generation hints

## Existing contracts

The deployed unmodified base records completed input counts, canonical fingerprints, response aliases, and pending-tool manifests. Model forks use irreversible internal keys; those keys cannot recover a logical parent identity. The new logical-generation hint improves lookup but cannot be required to consume state written by that base.

## Discover context without inferring ownership

On a local full-history resend without an explicit response or turn token, discover completed ordinary model forks in the caller's API-key scope if the selected row cannot establish the supplied context. Include normally CLOSED rows because orderly process replacement preserves their proof. Exclude file-pinned requests and goal-restart handling from discovery.

Compute canonical hashes for every proper input prefix, including the existing forwarding normalization of tool namespaces. Incremental hashing copies the SHA-256 state before appending the closing bracket, avoiding repeated serialization of overlapping prefixes. Query only matching hashes, in bounded parameter batches; unrelated rows cannot exhaust an arbitrary row cap. Recheck the stored count and exact fingerprint using the existing proof helper.

Validate retained prior output, direct tool settlement, the durable pending-tool manifest, and the complete projected payload. Require one qualifying proof. Duplicate qualifying rows remain guarded rather than selecting an arbitrary branch. This is deliberately conservative: no content-derived account ownership or alias reassociation is allowed.

Use the proof to authorize fresh projected execution. Clear its owner lookup before routing, never inject its upstream response or token, and select an eligible account normally. Retain the original client history fingerprint for the next completion, while dispatching its established account-neutral projection. Explicit response/turn anchors retain existing semantics; broad session/thread locality does not establish an upstream response owner.

## Fence execution across process replacement

Fresh recovery receives a durable operation fence without claiming a hard account-owned anchor. Its fingerprint covers API-key scope, stable client process/thread scope, and canonical projected request content. Preserve client-supplied prompt-cache keys; omit derived prompt-cache keys because the thread-anchor index mints them anew after process restart. Random recovery-session IDs and account installation metadata do not enter this identity.

Carry that fence through request re-preparation. Do not advance an unanchored inferred request from a latest-completed operation in another session: that would import ownership without an exact anchor. Existing operation admission then replays a complete terminal spool or refuses an unresolved dispatch; it never redispatches solely because the process or recovery lane changed. Existing same-owner accepted-lifecycle retry remains unchanged.

## Compatibility and verification

No schema migration, setting, required client field, or retrospective ownership backfill is introduced. The public-process probe creates long history and a compacted model fork on the unmodified deployed base, replaces the process with the patch against the same database, recovers without a token or generation hint, then replaces it with the base and continues using the ordinary returned token.

A second probe emits partial output then closes upstream before completion; after restarting the patch, identical history must not produce another upstream dispatch. Unit controls cover API-key isolation, CLOSED rows, unchanged aliases, more than 256 unrelated branches, chunked SQL parameters, exact prefix hashes, explicit anchors, file references, missing tools, and stable operation identity.

The baseline is the unmodified deployed source at f9c2cb51, not an independently verified official upstream tip. Public probes establish wire projection, routing, persistence, and restart behavior against a synthetic upstream; they do not establish live-model interpretation of lossy context. Deleted proofs and multiple qualifying proofs remain guarded.
