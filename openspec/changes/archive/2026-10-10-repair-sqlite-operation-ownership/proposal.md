## Why
Cancelled aiosqlite statements can retain native cursors and writer locks after Python connection close. NullPool additionally makes ordinary session teardown the last-close WAL checkpoint owner. Both faults were reproduced on the deployed database runtime.

## What Changes
- Own file-SQLite session driver operations through result consumption and cleanup; caller cancellation cannot cancel a running driver operation.
- Admit all local writes at the engine transaction boundary, bounded by the existing busy timeout, across main and background engines.
- Retain a fixed bounded connection pool rather than checkpoint on every session close.
- Share one renewal operation and fence late completion after leadership demotion.
- Preserve schema and official beta.8 database interchangeability.

## Capabilities
### Modified Capabilities
- `database-backends`: SQLite operation ownership, transaction admission and connection lifetime.

## Impact
Session factories, SQLite engine events, leader election, shutdown and public continuation regression coverage. No required configuration or migration.
