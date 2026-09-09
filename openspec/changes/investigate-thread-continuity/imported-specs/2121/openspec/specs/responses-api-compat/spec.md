@@ -3,7 +3,9 @@
 ## Purpose
 
 Define Responses API compatibility contracts so Codex, OpenCode, and OpenAI-style clients preserve expected behavior.
+
 ## Requirements
+
 ### Requirement: Use prompt_cache_key as OpenAI cache affinity
 For OpenAI-style `/v1/responses`, `/v1/responses/compact`, and chat-completions requests mapped onto Responses, the service MUST treat a non-empty `prompt_cache_key` as the bounded upstream account affinity key for prompt-cache correctness even when a `session_id` header is present. OpenAI-style route wiring MUST NOT upgrade those requests to durable `CODEX_SESSION` affinity by default. This affinity MUST apply even when dashboard `sticky_threads_enabled` is disabled, the service MUST continue forwarding the same `prompt_cache_key` upstream unchanged, and the stored affinity MUST expire after the configured freshness window so older keys can rebalance. The freshness window MUST come from dashboard settings so operators can adjust it without restart.
 
@@ -5536,6 +5538,7 @@ captured when the connection began.
 - **GIVEN** `prohibitFastMode` is enabled
 - **WHEN** an internal owner-forwarded payload carries a priority service tier
 - **THEN** the receiving preparation boundary omits `service_tier` before upstream forwarding
+
 ### Requirement: Native direct HTTP egress preserves Responses streaming semantics
 
 Direct Responses HTTP/SSE requests sent through native egress MUST preserve the existing normalized upstream payload and headers, rate-limit header ingestion, maximum SSE event size, idle and total request deadlines, terminal-event requirements, downstream event normalization, archives, and error envelope behavior. Downstream cancellation MUST cancel and await only the owned native request task, unregister its event stream, and leave unrelated multiplexed requests usable. Native transport selection MUST NOT change the public HTTP status or SSE framing contract.
@@ -5731,3 +5734,42 @@ rule. A missing or invalid value MUST remain absent.
 - **WHEN** an upstream retry hint contains a line break or exceeds the bounded
   field length
 - **THEN** codex-lb does not copy that value downstream
+
+### Requirement: Exact tool-manifest replay preserves fresh user follow-up
+
+When a fingerprint-verified durable input prefix is followed by every call and
+matching output in the durable prior-response pending-tool manifest, the
+full-resend context proof SHALL permit trailing self-contained user input after
+that complete batch. The proof MUST require exact call IDs and call types,
+complete settlement, no duplicate or orphan result, and no call-ID collision
+with the stored prefix. It MUST reject user input interleaved with the batch or
+any later call, output, or instruction-role message after the fresh-input suffix
+begins. The existing bounded developer-interleave exception MUST NOT gain a
+trailing-input extension.
+
+Account switching MUST still require the complete projected request to pass
+account-neutral replay classification, the durable prefix to match, and the
+existing pre-dispatch recovery and account-scope checks. A qualifying replay
+MUST retain the complete calls, outputs, and fresh input. This proof MUST NOT
+authorize transferring encrypted compaction, account-owned files, conversation
+references, or an unverified input prefix.
+
+#### Scenario: Goal follow-up after completed tool batch can leave exhausted owner
+
+- **GIVEN** the input contains a verified stored prefix and exactly settles its durable pending-tool manifest
+- **AND** a self-contained goal-continuation user message follows the complete tool batch
+- **WHEN** the previous owner is unavailable before dispatch and the complete projected body is account-neutral
+- **THEN** the bridge can use its existing fresh replay path on another eligible account
+- **AND** it retains the calls, results, and goal instruction without the old response anchor
+
+#### Scenario: Fresh input does not conceal a missing parallel result
+
+- **GIVEN** a durable manifest contains multiple calls
+- **WHEN** a resend appends user input after only part of the recorded batch
+- **THEN** context proof fails and cross-account replay remains forbidden
+
+#### Scenario: New input does not relax developer-interleave bounds
+
+- **GIVEN** a suffix uses the existing three-item custom-call/developer/output exception
+- **WHEN** additional user input follows that suffix
+- **THEN** this exception remains ineligible for exact-manifest proof