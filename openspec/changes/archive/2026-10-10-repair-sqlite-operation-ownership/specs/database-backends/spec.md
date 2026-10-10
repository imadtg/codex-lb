## REMOVED Requirements
### Requirement: File-backed SQLite engines do not retain idle pooled descriptors
**Reason**: Last-close checkpoints can block the writer slot during ordinary teardown. Replaced by bounded retained pools.
**Migration**: No schema migration; file-SQLite factories use the new bounded default.

## MODIFIED Requirements
### Requirement: SQLite account writes share the local writer section
SQLite account mutation paths SHALL use shared engine transaction admission before performing database writes, including account import/upsert, reauthentication, token persistence, status transitions, dashboard preferences and deletion. Legacy writer section scopes SHALL remain callable without adding a second mutex. PostgreSQL transaction and advisory-lock behavior SHALL remain unchanged.

#### Scenario: Account persistence shares admission with coordination writes
- **WHEN** an account mutation uses an application file-SQLite session
- **THEN** engine admission serializes its transaction with background coordination writes

#### Scenario: Account token persistence is serialized on SQLite
- **WHEN** a token refresh persists encrypted token values through an application file-SQLite session
- **THEN** engine transaction admission serializes its write

#### Scenario: Account status persistence is serialized on SQLite
- **WHEN** an account status transition is persisted through an application file-SQLite session
- **THEN** engine transaction admission serializes its write

## ADDED Requirements
### Requirement: File-backed SQLite engines retain bounded pools
File-backed SQLite main and background engines MUST retain bounded pools of four connections with zero overflow and a finite checkout timeout. Session closure MUST return a connection without physically closing the final SQLite connection on every transaction. Existing WAL, synchronous and busy-timeout tuning MUST remain enabled. In-memory SQLite MUST preserve shared-engine behavior and PostgreSQL pooling MUST remain unchanged.

#### Scenario: Ordinary session teardown retains connections
- **WHEN** a file-SQLite session commits and closes
- **THEN** its connection is returned to the bounded pool
- **AND** ordinary close does not cause a last-connection checkpoint

### Requirement: SQLite driver operation ownership survives cancellation
File-SQLite application sessions MUST own running driver operations until their result is consumed and transaction cleanup completes. Caller cancellation MUST NOT interrupt driver execution, RETURNING result collection, commit or rollback. Concurrent use of one session MUST be rejected. Shutdown MUST drain owned operations before disposal, and MUST report unclean rather than reclaim a connection still in use.

#### Scenario: Cancellation during a blocked writer
- **WHEN** a caller is cancelled while SQLite is executing a write
- **AND** the driver subsequently completes
- **THEN** the operation result and cleanup complete before cancellation propagates
- **AND** an independent writer recovers without garbage collection or restart

### Requirement: SQLite writes share transaction admission
All file-SQLite writes through configured main and background engines MUST share admission keyed by resolved database path. Admission MUST precede the first write and remain held until connection checkin after transaction cleanup. Within an explicit writer section, admission MUST precede the first database statement, including mutation predicate reads. Admission wait MUST be finite. Legacy writer section scopes MUST NOT introduce a second lock order.

#### Scenario: Coordination and request writes contend
- **WHEN** a background renewal owns an unfinished write transaction
- **THEN** another local writer waits within the admission bound
- **AND** read-only operations remain concurrent

### Requirement: Late renewal cannot resurrect local leadership
Renewal observers MUST share one in-flight driver operation. Cancelling or timing out an observer MUST NOT cancel that owner. A renewal completed after local demotion MUST NOT publish leadership or a new local deadline.

#### Scenario: Demotion while renewal is blocked
- **WHEN** leadership is demoted while a renewal remains in flight
- **AND** the database later returns a successful renewal result
- **THEN** the instance remains locally demoted
