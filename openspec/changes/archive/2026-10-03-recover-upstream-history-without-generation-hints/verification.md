# Verification: recover-upstream-history-without-generation-hints

Verified locally on 2026-10-03 against unmodified deployed base f9c2cb51f1402c8069f541cbc364386a33c4610f. No production deployment, restart, branch, commit, push, or PR was performed.

## Completeness, correctness, and coherence

All six tasks and both delta requirements are complete. Main requirements and context are synchronized. No unresolved critical implementation issue remains.

| Requirement/scenario | Implementation | Evidence |
| --- | --- | --- |
| Missing generation hint | Scoped completed-fork query and exact prefix/projection proof in streaming.py | Unmodified base → patch → unmodified base public-process test |
| Ordinary return token | Existing completion and alias contracts; no schema change | Base follow-up completes on the alternate with four total upstream requests |
| Explicit anchors and API-key isolation | Discovery excludes explicit turn/response anchors; repository scope predicate | Unit anchor/scope controls and five existing HTTP integration controls |
| Tool/file restrictions | Durable pending-call manifest validation and full projected payload eligibility; file-owner gating | Missing-tool/file unit controls and public missing-output/accepted/visible controls |
| Ambiguous proof identity | Multiple qualifying proofs refuse inference | Duplicate-source unit control; aliases remain unchanged after discovery |
| More than 256 unrelated rows | Incremental canonical proper-prefix hashing and SQL fingerprint filtering in parameter batches | CLOSED legacy rows, 300 unrelated branches, repeated fingerprints across SQL batches |
| Interrupted recovery and restart | Stable scoped operation fingerprint, inherited fence, no unanchored latest-operation advancement | Partial output plus upstream close; restart refuses identical request with 503 upstream_operation_status_unknown and stays at three upstream requests |
| Current model generation | Optional hint, existing exact alias precedence and atomic completion | Existing generation publication tests and public model-compaction regressions |

The implementation reuses established projection, pending-tool validation, durable operation admission, and existing wire/schema contracts. Read-only discovery neither creates nor moves aliases and does not import content-derived ownership.

## Regression progression

The first repair failed the shared-database legacy continuation without a generation hint; retained red evidence is in ../regression-evidence/build-swap-red/ relative to the source root. The new path passes both compatibility process tests.

The new interruption control also exposed a duplicate dispatch after restart: a derived prompt-cache key was reminted by the process-local thread-anchor index, changing the ordinary wire fingerprint. The repair uses canonical projected request content, API-key scope and stable client scope, retaining explicit cache keys while excluding derived cache locality. It also excludes unanchored history recovery from latest-completed-operation anchor advancement. After the repair the same retry returns the existing unresolved-operation error and makes no new upstream request.

The control emits partial output before its close because existing same-owner accepted-lifecycle replay is intentional when only response.created has arrived. That behavior remains unchanged.

## Final results

- All 31 public process scenarios passed in two disjoint pytest process shards: 16 and 15 passes. Both build-swap cases are included.
- Relevant replay safety, ID stripping, portability, quota admission, durable sessions, and replay rejection suites: 430 passed.
- The 14 new history/operation helper cases passed again after typing-only corrections.
- Five existing HTTP integration controls passed: model-change explicit response reuse, exact turn-token alias ownership, API-key token isolation, no pre-admission alias publication, and different-model follower isolation.
- Ruff lint, Ruff formatting for all 17 changed Python files, and git diff --check passed.
- Strict change validation and all 65 main capability specifications passed.
- Whole-checkout type checking remains failing with 29 existing diagnostics; the unmodified base has 31. Normalized diagnostic comparison found no new errors or warnings.

Commands:

```sh
uv run --no-sync pytest -q tests/unit/test_replay_safety.py tests/unit/test_replay_safety_strip_ids.py tests/unit/test_replay_safety_portability.py tests/unit/test_quota_handoff_admission.py tests/unit/test_durable_bridge_sessions.py tests/unit/test_http_bridge_replay_rejection.py
uv run --no-sync pytest -q tests/integration/test_quota_handoff_blackbox.py
bunx --yes @fission-ai/openspec@1.11.0 validate recover-upstream-history-without-generation-hints --strict
bunx --yes @fission-ai/openspec@1.11.0 validate --specs --strict
```

The public suite's final run partitioned its 31 exact pytest node IDs into two disjoint processes. Synthetic reports, request logs, application/probe fingerprints, and a 31-scenario manifest are retained in ../regression-evidence/compat-final/. Type comparison is in ../typecheck-compat-comparison.txt and detailed diagnostics in ../typecheck-patched-compat.txt.

## Practical limits

The tested baseline is the unmodified deployed build, not an independently verified official upstream tip. These tests establish shared-database state compatibility and synthetic upstream wire/routing behavior; they do not measure a live model's interpretation of lossy projected context. Deleted completed proofs and multiple qualifying proofs remain guarded. An unresolved accepted operation is refused because its execution status cannot be proven; the test verifies that available quota does not authorize duplicate execution.
