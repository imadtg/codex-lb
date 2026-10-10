## ADDED Requirements

### Requirement: Sustained SQLite write failure is visible to readiness

After repeated file-backed SQLite busy failures over at least the configured busy timeout, the system SHALL check writer-slot acquisition on a fresh connection with a bounded wait. A failed acquisition SHALL emit a rate-limited sqlite_writer_slot_held diagnostic and cause infrastructure readiness to return 503. Successful acquisition SHALL roll back, close the probe connection, and clear the writer degradation. Healthy operation SHALL NOT perform these probes. Probe tasks SHALL have explicit ownership; concurrent readiness requests SHALL share one probe. Non-lock probe failures SHALL remain distinguishable from writer contention. PostgreSQL and in-memory SQLite SHALL remain unaffected.

#### Scenario: Reads succeed while the writer remains unavailable

- **GIVEN** repeated write failures beyond the busy timeout and successful SELECT queries
- **WHEN** a fresh bounded BEGIN IMMEDIATE also fails
- **THEN** readiness returns 503 and a diagnostic reports loss of write capability without asserting lock ownership

#### Scenario: Transient contention or subsequent recovery

- **GIVEN** brief contention or a writer that has subsequently released its transaction
- **WHEN** the sustained-failure threshold has not been reached or a later probe acquires the writer slot
- **THEN** contention alone does not fail readiness, and successful probe acquisition clears previous writer degradation
