# Preserve complete history on account handoff

## Why
Two real Codex full-resend endings were rejected after their owner exhausted quota: a completed final answer followed by a developer instruction and the next user message; and encrypted reasoning plus commentary followed by an exactly settled tool call and the next user message. The durable bridge returned `previous_response_owner_unavailable` despite another eligible account. An adjacent pre-visible HTTP retry also moved an unsettled tool call to another account, contrary to its existing process test.

## What Changes
Recognize exactly one valid developer instruction between a completed final assistant answer and one fresh user message. In the exact persisted tool-manifest proof, treat validated reasoning and search records as context surrounding the tool batch. Preserve all substantive history and remove only response-owned top-level item IDs in the existing cross-account projection. Require complete account-neutral input before ordinary HTTP quota or permanent-account rejection handoff.

## Scope
ChatGPT-account to ChatGPT-account replay only. Other developer positions, unsettled tools, malformed content, and provider/model-source replay retain their current guards.
