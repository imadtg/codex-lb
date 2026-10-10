## ADDED Requirements

### Requirement: HTTP bridge transcript accumulation deadlines

The transcript worker MUST flush a nonterminal batch when its oldest pending
event reaches the configured interval or its operation reaches the batch-size
threshold. Later arrivals MUST NOT postpone that oldest-event deadline.
Wakeups MUST recompute eligibility rather than flush every pending operation.
Eligibility MUST be rechecked after acquiring flush serialization.

#### Scenario: Paced events accumulate

- **WHEN** nonterminal events arrive on separate scheduler turns below the threshold
- **THEN** they accumulate until the oldest pending event becomes due
- **AND** downstream event delivery proceeds independently of accumulation

#### Scenario: Batch-size threshold flushes early

- **WHEN** an operation reaches the batch-size threshold before its deadline
- **THEN** its next background batch becomes eligible immediately

#### Scenario: Remainder retains its own oldest deadline

- **WHEN** a flush leaves a sub-threshold remainder
- **THEN** the remainder's deadline uses its oldest event's original enqueue time

### Requirement: HTTP bridge accumulation preserves drain and replay fences

Explicit drains and terminal persistence MUST bypass accumulation delay.
Each worker pass MUST service at most one batch per eligible operation before
reconsidering readiness. Overflow, failed writes and process interruption MUST
NOT make an incomplete transcript eligible for completed replay.

#### Scenario: Terminal bypasses the interval

- **WHEN** a terminal append arrives with nonterminal events queued
- **THEN** pending events drain in order without waiting for the interval
- **AND** existing owner, attempt and completion fences still apply

#### Scenario: Busy operation shares service with quiet operation

- **WHEN** multiple operations have eligible events
- **THEN** one operation's backlog does not drain entirely ahead of the others

### Requirement: HTTP bridge batch diagnostics are bounded

Optional Prometheus diagnostics MUST expose batch outcomes, committed event
counts and bytes, oldest-event queue age and append duration. Labels MUST be
limited to storage format, flush reason and outcome; diagnostics MUST NOT
contain request, operation, session, account identifiers or event content.

#### Scenario: Successful append records committed batch size

- **WHEN** a repository append succeeds
- **THEN** diagnostics record one successful batch and its event and byte counts

#### Scenario: Rejected append is not counted as committed

- **WHEN** a repository append fails or is fenced
- **THEN** diagnostics record its outcome without adding committed events
