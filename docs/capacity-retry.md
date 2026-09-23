# Output-free model-capacity retries

The T3 thread `0baf57fa-aac9-4e47-b421-acae1747ed33` recorded repeated
`server_is_overloaded` failures for ordinary HTTP streaming. The useful
distinction was that these were model-capacity responses, not account quota
failures. The captured diagnosis showed a stream shaped like:

1. `response.created`
2. `response.in_progress`
3. an output-free capacity terminal (`server_is_overloaded`,
   `overloaded_error`, or the selected-model capacity message)

The existing retry loop correctly refused to replay after the first frames had
already been delivered to the client: replaying then would expose two response
lifecycles. The bridge/WebSocket implementation already had a single-lifecycle
replay for its equivalent accepted-output-free case, but the ordinary HTTP
stream path did not retain the provisional prelude.

The fork now implements the safe fix by buffering only
`response.created` and `response.in_progress` until the turn produces
substantive output or a non-capacity terminal. If an output-free capacity
terminal arrives while that prefix is buffered, the normal transient retry
signal can be raised before yielding the prefix. The existing bounded
same-account retry machinery can then retry the request; if it later fails,
normal failover and health handling apply. Once a turn is known to be real, the
prefix must be flushed exactly once and all existing no-replay rules must remain
unchanged. We have deliberately not implemented a retry after a prefix has
already been delivered, because that would expose duplicate lifecycles.

The diagnostic markers are:

```text
stream_accepted_capacity_retry request_id=… account_id=… buffered_events=… code=…
```

It contains no prompt or response content. The black-box regression
`test_stream_accepted_output_free_capacity_retries_before_lifecycle_visible`
drives the same HTTP sequence through the public endpoint and proves that the
client sees one lifecycle after the retry. The retry is bounded by the existing
same-account transient retry budget; if that budget is exhausted, the normal
terminal error is surfaced and no provisional prefix is emitted twice.

Capacity is retryable only while the stream has emitted the provisional
`response.created`/`response.in_progress` prelude and no substantive output.
Once output is visible, or when the terminal has no provisional prelude, the
existing fail-closed behavior remains in force because replay could duplicate
work. The implementation logs the staging event above; the ordinary retry
logger records each retry and the terminal settlement logger records an
exhausted/surfaced attempt, allowing operators to distinguish successful
recovery from a bounded failure without recording prompt content.
Existing tests for terminal capacity errors without a provisional prefix
continue to assert that they are surfaced without replay.
