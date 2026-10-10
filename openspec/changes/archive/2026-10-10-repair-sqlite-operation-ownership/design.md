## Decisions
Use a cancellation-deferring AsyncSession for file SQLite. A single driver operation owns a session at a time; repeated cancellation finishes that operation, consumes its result, then rolls back and closes before surfacing cancellation. Concurrent session use is rejected.

Use engine before_cursor_execute admission and checkin release, keyed by resolved database path and event loop. This includes ORM autoflush and raw coordination SQL. Admission waits at most the existing 30-second busy timeout. The bounded pools also bound active driver workers. Legacy writer sections mark a scope whose first database statement (including a mutation predicate SELECT) claims engine admission. Retaining their separate mutex would introduce lock-order inversions when a session already owns a write transaction. The inherited context contains only a boolean; each connection claims admission independently, so child tasks cannot inherit lock reentrancy.

Retain four connections per engine, zero overflow, finite checkout wait. Preserve WAL/NORMAL and automatic checkpoint policy. This removes per-session last-close checkpoints; commit-time and storage stalls remain possible and readiness must stay truthful.

Renewal observers share a single owned operation. Demotion increments a generation; a late result cannot publish a local lease deadline in a newer generation. Cancellation detaches an observer, not the renewal owner.

Shutdown drains owned operations before disposal. If native work exceeds the shutdown grace, report unclean and leave its connection owned; never close or invalidate concurrently.

## Compatibility
No schema or persisted representation changes. PostgreSQL and in-memory SQLite keep their existing factories and pool behavior. Same database remains usable by official beta.8.
