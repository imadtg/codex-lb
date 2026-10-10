# Verification: repair-projected-model-transition-recovery

Verified locally on 2026-10-03 against deployed-source commit f9c2cb51f1402c8069f541cbc364386a33c4610f. Production was not changed.

## Completeness and correctness

All eight tasks and three requirements are complete. The implementation matches the design and reuses the existing projection, durable operation admission, owner-fenced alias publication, and alias conflict predicates.

| Requirement | Implementation | Regression evidence |
| --- | --- | --- |
| Developer instruction block remains portable | replay_safety.py settled-output suffix validator | Public model_switch_developer_block; five positive/negative boundary tests |
| Turn-token continuations obtain a durable fence and recover quota | request_submit.py operation registration; upstream_events.py rejection/retry ownership; continuity.py and repository alias policy | Public quota_bridge_model_compaction_turn_state; ordinary fork alias protection and competing recovery tests |
| Completed model generation survives transport closure | request state identity; scoped coordinator lookup; atomic repository completion publication | Public model_compaction_retry; scoped generation lookup; explicit old anchors; fenced/protected publication failure |

## Public-process results

The same current probe was rerun against an unmodified source extraction, using the shared Python dependencies and explicit checkout PYTHONPATH. Git reported no application diff in that baseline.

- All three incident regressions failed against the baseline and passed against the patch, including the subsequent request on the alternate account.
- The 29-scenario broad run produced 27 passes and two failures in older replacement fixtures.
- Both fixture failures also reproduced against baseline. A missing-response error leaves the original account eligible, so the old fixture incorrectly depended on random alternate selection.
- After deterministically pausing that owner through the public API, all three replacement controls passed against both baseline and patched builds. Their completion, rejection, ambiguity, and no-duplicate-execution assertions remain intact.
- All 29 distinct public scenarios have therefore passed across these runs. A second monolithic run was unnecessary after the fixture-only correction.

Commands:

```sh
uv run --no-sync pytest -q tests/integration/test_quota_handoff_blackbox.py
uv run --no-sync pytest -q tests/integration/test_quota_handoff_blackbox.py -k 'replacement_'
uv run --no-sync pytest -q tests/integration/test_quota_handoff_blackbox.py -k 'model_switch_developer_block or model_compaction'
```

Set CODEX_LB_BLACKBOX_CHECKOUT to the baseline checkout to reproduce the red incident tests. Retained synthetic reports and server logs are outside the source checkout in ../regression-evidence/. Temporary pytest artifacts from earlier runs were removed by pytest retention.

## Focused tests and static checks

- Relevant replay, portability, quota admission, durable session, and replay rejection suites: 410 passed.
- Additional developer-block boundary tests: five passed.
- Selected existing HTTP bridge integration cases for model isolation, exact token ownership, API-key isolation, and pre-admission alias publication: five passed.
- Ruff lint and formatting of changed Python files: passed.
- git diff --check: passed.
- Strict change validation and all 65 existing OpenSpec capability validations: passed before synchronization; synchronization/archive validates the resulting specification again.
- Whole-checkout type checking remains failing: baseline 31 diagnostics, patched 29, no newly introduced diagnostics. The changed probe passes its focused type check. Details are saved outside the checkout in ../typecheck-comparison.txt.

## Coherence and practical limits

No unresolved critical implementation issues or uncovered delta scenarios remain. The projection retains instructions; quota handoff remains fenced; explicit aliases outrank the new generation hint. Live recovery lanes cannot steal each other's token aliases. This change uses the existing schema and adds no operator settings.

Generation hints are populated by successful completions. Historical forks without a hint or matching explicit anchor are not retrospectively associated with a logical thread, and deleted history proofs are not reconstructed. Concurrent completions advance the hint in publication order; exact anchors and history matching still apply. Public-process tests verify request projection/routing against a synthetic upstream, not live-model interpretation of lossy context.
