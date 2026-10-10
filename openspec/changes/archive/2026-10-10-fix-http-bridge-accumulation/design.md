## Context

Paced events currently wake the worker into an immediate write. The existing
interval bounds an idle wait, and batch size caps extraction rather than
triggering accumulation. Production logs also contain terminal persistence
timeouts; they do not establish the underlying disk-stall cause.

## Decisions

Use one monotonic enqueue timestamp on each pending event. The queue itself
owns deadline state, so removing or fencing events cannot leave stale timers.
One worker computes eligible operations and its next wake deadline. Each pass
takes at most one batch per eligible operation. Eligibility is rechecked after
acquiring the flush lock, covering terminal-drain and discard races. Wakeups
recompute readiness; later arrivals never reset the oldest event's timestamp.

Terminal drains retain the existing bypass and serialization. Queue overflow,
failed writes and interruption retain incomplete-spool behavior. Successful
append metrics count repository-confirmed batches, not all database commits.

The writer format continues to default to rows. Existing chunks are evaluated
with the same stimulus and exact supported base; no migration is introduced.

## Failure Modes and Verification

Test continuous sub-threshold arrivals, threshold flushes, remainder deadlines,
concurrent operations, terminal drains, failed writes, overflow and cancellation.
A separate public application process uses a paced synthetic upstream and a
disposable SQLite database. Observe exported batch metrics, exact persisted
event text and completed replay across a supported base/fork swap. For example,
events 25 ms apart should group at the unchanged 100 ms interval while each
delta is still delivered immediately to the client.

The interval bounds scheduling eligibility, not disk commit latency. A failed
or interrupted transcript must never become replayable as complete. Reducing
transactions is not proof of eliminating storage stalls or missing context.
