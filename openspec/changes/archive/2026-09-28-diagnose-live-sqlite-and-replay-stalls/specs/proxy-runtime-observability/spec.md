## ADDED Requirements

### Requirement: SQLite lock failures identify live write holders

When a file-backed SQLite write fails because the database is busy or locked, the proxy SHALL report a bounded summary of live write transactions it has observed in the process, across request and background engines. The summary SHALL include each candidate holder’s age, owning task, and SQL operation class. It SHALL omit bound parameters, model content, credentials, and raw SQL values. A successful commit or rollback SHALL remove the transaction from the live-holder set. Absence of an observed holder SHALL be explicit and SHALL not be presented as proof that no holder exists outside the process.

#### Scenario: A live holder blocks another write
- **GIVEN** one task has successfully written in a SQLite transaction and keeps it open
- **WHEN** another task attempts a write and receives `SQLITE_BUSY`
- **THEN** the diagnostic names the live holder’s operation class and age without logging query parameters

#### Scenario: The holder releases its transaction
- **GIVEN** a live holder has been reported
- **WHEN** its transaction commits or rolls back
- **THEN** subsequent lock diagnostics do not report that transaction as active

### Requirement: Rejected durable-prefix proofs expose content-free mismatch evidence

When an unavailable owner cannot hand off a full resend because its prefix fingerprint differs from the durable anchor, the proxy SHALL log the stored and incoming item counts and bounded fingerprints of the compared prefixes. It SHALL not log message text, encrypted content, tool output, credentials, or raw request JSON. Diagnostics SHALL not relax the existing handoff proof.

#### Scenario: A full resend has a different prefix
- **GIVEN** a durable anchor with a stored prefix fingerprint
- **WHEN** an owner-unavailable request contains a different prefix
- **THEN** the rejection log records enough content-free evidence to distinguish length mismatch from value mismatch
- **AND** the account handoff remains rejected
