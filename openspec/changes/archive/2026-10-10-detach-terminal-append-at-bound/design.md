# Design

The spooler owns each terminal append task until completion. Waiting uses a bounded observation without cancelling that task on timeout or caller cancellation. Existing durable attempt/phase fences remain responsible for preventing a late append from reopening a settled attempt. This avoids interrupting a real SQLite write transaction while preserving bounded client settlement.

Verification covers both expiry and caller cancellation against real aiosqlite transactions, plus late-settlement and attempt-fence controls. No schema or configuration change is required.
