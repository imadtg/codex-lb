# Repair projected model-transition recovery

## Why

Oct 3 request traces show complete client history blocked by consecutive harness developer messages, and a turn-state continuation blocked from quota handoff because it was never registered as an operation. After model change and compaction, a retry also resolves an older conversation generation. Recoverable context should be projected before account selection; response bookkeeping must not create an owner dependency.

## What Changes

- Add public-process regressions for model-change instruction blocks, turn-state operation admission, and retry after model change/compaction.
- Permit validated plaintext developer instruction blocks around a settled final-answer/user boundary.
- Fence turn-state continuations even when the client omits previous_response_id.
- Preserve the current conversation generation through model-isolated forks and subsequent full-history requests.

## Impact

Responses compatibility and durable HTTP bridge recovery. Keep single execution, file ownership, tool settlement and ambiguous-dispatch rules. No production rollout in this change.
