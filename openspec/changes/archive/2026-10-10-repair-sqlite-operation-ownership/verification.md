# SQLite ownership repair — verification

## Scope

Source: `../fork-path-20261010/candidate`.
Final wheel: `deployment/codex_lb-1.25.0b8-py3-none-any.whl`.
Release: `sqlite-ownership-20261010-de1a76c62ad0`.

The repair owns file-SQLite session operations through result collection and cleanup, admits transactions through one gate per resolved database path, preserves mutation predicate scopes, retains four connections per engine with zero overflow, fences late leader renewal results, and isolates heartbeat maintenance failures. No schema, static asset, configuration requirement or dependency change.

## Evidence

- `final-focused-tests-v2.log`: 146 passed (scheduler, session teardown, admission, cancellation, readiness, terminal append and public error attribution).
- `final-production-stack-tests.log`: 13 passed on Python 3.14.7 / SQLite 3.53.4 / SQLAlchemy 2.1.3 / aiosqlite 0.22.1.
- `public-process/summary.json`: all 29 catalog cases passed before the final predicate-scope adjustment. Covers history projection, quota/owner handoff, ambiguous acceptance, tools, agent input, reasoning and compaction.
- `final-native-cancel-public/report.json`: final application source; three cancelled real SQLite statements during quota completion; tool commentary and follow-up recover, cancelled writes roll back, independent writer succeeds, readiness returns 200.
- `checkpoint-lab-results.json`: disposable bounded native fsync pause reproduces NullPool last-close lock and proves bounded retained pool avoids that session-close checkpoint.
- `commit-checkpoint-results.json`: actual commit fsync pause retains driver ownership through cancellation; readiness fails while blocked and recovers after release; both engines write afterward. A pinned reader grows WAL to 358472 bytes under the bounded workload; after reader release, checkpoint truncates it to zero. This is not a guarantee of bounded WAL with indefinitely pinned readers.
- `base-fork-base-v2/report.json`: official beta.8 → fork → official beta.8 using one database/thread, under external writer contention, passes.
- `fork-base-fork-healthy/report.json`: fork → official beta.8 → fork using one database/thread, passes ordinary continuation. Upstream beta.8 does not acquire the fork's compaction recovery repairs merely by sharing a database; `fork-base-fork-v2/report.json` records that expected unsupported recovery path.
- `build-swap-pytest.log`: both original build-swap regressions pass after allowing their subprocess harness to finish (the broad 50-second pytest bound was shorter than the multi-process scenarios).
- `spec-final.log`, `lint-final.log`: strict change specification and scoped lint pass.
- `types-final.log` compared with `baseline-types.log`: one existing watchdog WeakKeyDictionary typing error in each; no new diagnostics.

## Baseline comparisons and limits

The broad product run initially produced 266 passes and nine failures. Six bridge mock/contract or hanging recovery failures reproduce on the saved deployed source (`baseline-failures.xml`). Two build-swap failures were outer test timeout failures and pass with the corrected test bound. The remaining public request-log race was exposed by the new scheduling/admission behavior; the final scope repair restores predicate serialization and that regression passes on both runtime stacks. The deterministic inherited-child predicate regression also proves scopes do not grant lock reentrancy to another session.

The full broad product suite is not claimed green. No production payloads or credentials were used in regression scenarios. Fault preload libraries were injected only into disposable local child processes.

## Deployment

Independent normal restart completed at 12:59:52 UTC. Release `sqlite-ownership-20261010-de1a76c62ad0` is live as PID 3557157; readiness, dashboard and hub return 200. All 815 running source/resource hashes match. Fresh BEGIN IMMEDIATE acquisition rolls back successfully, and no uninterruptible threads were present in the sampled process. Quick checking remains enabled. The release installer verifies all 815 packaged source/resource files, unchanged schema files and dependency versions before a disposable application smoke. Smoke startup allowance is 300 seconds: the first 90-second cold migration allowance was insufficient on Redarchy; no application startup check setting was disabled.

## Live trace observations

`deployment/production-verification.json` and `deployment/writer-verification.json` record runtime and writer checks. The initial post-deployment journal sample contains no database locks, writer-slot/probe failures, heartbeat failures or request-log persistence failures.

`deployment/post-restart-traces.json` shows a stale previous-response failure at 13:00:01 UTC for one hashed request scope. That scope then completed at 13:00:59 with replay_count=1 and 407 response events, followed by completed turns with replay_count=0 at 13:01:35, 13:02:11 and 13:03:01. Thus the observed stale-anchor event was followed by recovery; it is not counted as an absent upstream error. Pricing-catalog warnings came from an independent metadata fetch.

The observation window is minutes, not proof that no future storage or provider fault can occur. The six baseline bridge test failures remain recorded; the full broad suite is not claimed green.

The OpenSpec change was verified, synced into database-backends, and archived as `2026-10-10-repair-sqlite-operation-ownership`.
