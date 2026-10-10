The implementation starts from the preserved October 3 fork plus its deployed local repairs. It retains encrypted reasoning, compaction, completed search context, agent messages, and complete local tool histories wherever the backend accepts projection. Upstream tests expecting reasoning omission must be adapted.

Example: a code-less response.failed frame asserting that the usage limit is reached must use the same exhausted-account health and failover behavior as usage_limit_reached, including API-key settlement before health writes. An invalid_request_error echoing those words must remain a request rejection.

The writer readiness probe uses a fresh, short-timeout SQLite connection and BEGIN IMMEDIATE followed by rollback, after persistent busy errors. Successful probe clears the degraded writer state. It is evidence of write capability, not proof of which connection owns a lock. Normal brief contention does not immediately make readiness fail. PostgreSQL and in-memory SQLite behavior remains unchanged.

Deployment uses the normal service restart and existing default quick-check behavior. No drain endpoint choreography or startup-check override is added.
