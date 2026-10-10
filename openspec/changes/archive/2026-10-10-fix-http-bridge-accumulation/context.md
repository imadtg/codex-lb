# HTTP bridge accumulation verification

The previous enqueue wakeup immediately flushed partial batches. The worker
now uses the oldest pending event's monotonic deadline or the configured batch
threshold, with eligibility rechecked under serialization. Terminal drains
bypass the delay. Cancellation of an extracted append fences spool completion.
No storage schema, writer default or checkpoint policy changes.

A separate-process paced stream with 36 events compared the deployed baseline
and the candidate at the unchanged 100 ms interval. The baseline recorded 31
WAL transactions / 254 frames; the candidate recorded 17 / 153. All 35
nonterminal events persisted in seven batches. Total WAL transactions include
other request/background writes and are not a transcript-only counter.

Existing chunk mode stored eight chunks / 1,339 payload bytes instead of 36
rows / 6,486 bytes, with identical decoded transcript hashes. It remains opt-in.
Official beta.8 replayed candidate chunks without upstream dispatch; candidate
replayed official rows, preserving both formats in one database. This check
uses a stable client cache key. The upstream auto-key index mints a new cache
key after restart, and that key participates in operation fingerprints: an
initial check without a client key redispatched the identical request. This
is an existing identity limitation, independent of rows versus chunks. It is
not fixed or hidden by the accumulation change.

Verification includes 47 accumulation/batcher/metrics unit tests, 170 database,
terminal-writer and codec tests, public row/chunk concurrent streaming and
process interruption, and three public historical continuity regressions.
Delta delivery is measured separately from terminal persistence: the existing
terminal append bound permits a longer terminal delay than a normal delta.
Lint, scoped typing and strict change validation passed. Standard spec
validation passed 65 items; inherited length warnings remain.

Redarchy also passed 49 focused accumulation, metrics, batcher and native
terminal-writer tests on its existing Python 3.13.15 / SQLite 3.53.1 stack.
