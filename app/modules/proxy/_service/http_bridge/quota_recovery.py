"""Admission for explicit quota rejection; transport ambiguity never qualifies."""

from __future__ import annotations

from collections.abc import Callable

from app.modules.proxy._service.support import _WebSocketRequestState

_EXPLICIT_QUOTA_REJECTIONS = frozenset(
    {"usage_limit_reached", "insufficient_quota", "quota_exceeded", "usage_not_included", "rate_limit_exceeded"}
)


def quota_attempt_rejection_reason(request: _WebSocketRequestState | None, error_code: str | None) -> str | None:
    if error_code not in _EXPLICIT_QUOTA_REJECTIONS:
        return "not_explicit_quota"
    if request is None or not request.operation_registered:
        return "operation_unregistered"
    if request.response_id is not None or request.response_event_count > 0 or request.downstream_visible:
        return "output_started"
    if request.replay_count > 0:
        return "already_replayed"
    return None


def quota_handoff_rejection_reason(
    request: _WebSocketRequestState,
    error_code: str | None,
    *,
    operation_fenced: bool,
    other_requests_pending: bool,
    file_bound: bool,
    context_proven: Callable[[], bool],
) -> str | None:
    reason = quota_attempt_rejection_reason(request, error_code)
    if reason is not None:
        return reason
    if not operation_fenced:
        return "operation_fence_missing"
    if other_requests_pending:
        return "other_requests_pending"
    # A resolved turn token routes to the old owner; it is not itself missing
    # context. The fenced recovery lane preserves its downstream alias and
    # strips upstream affinity after complete portable history is proven.
    if file_bound:
        return "file_bound"
    if not context_proven():
        return "portable_context_unproven"
    return None
