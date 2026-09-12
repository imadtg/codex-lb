from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.modules.proxy._service.http_bridge.quota_recovery import quota_handoff_rejection_reason
from app.modules.proxy._service.support import _WebSocketRequestState

pytestmark = pytest.mark.unit


def request():
    return _WebSocketRequestState(
        request_id="test",
        model="gpt-6-astra",
        service_tier=None,
        reasoning_effort=None,
        api_key_reservation=None,
        started_at=0,
        operation_registered=True,
    )


@pytest.mark.parametrize(
    "code", ["usage_limit_reached", "insufficient_quota", "quota_exceeded", "usage_not_included", "rate_limit_exceeded"]
)
def test_only_a_proven_precreated_attempt_can_use_quota_handoff(code):
    assert (
        quota_handoff_rejection_reason(
            request(),
            code,
            operation_fenced=True,
            other_requests_pending=False,
            file_bound=False,
            context_proven=lambda: True,
        )
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_registered": False},
        {"response_id": "resp_accepted"},
        {"response_event_count": 1},
        {"downstream_visible": True},
        {"replay_count": 1},
    ],
)
def test_accepted_or_replayed_operations_never_reach_history_projection(changes):
    proof = Mock(side_effect=AssertionError("History must not override operation admission"))
    assert (
        quota_handoff_rejection_reason(
            replace(request(), **changes),
            "usage_limit_reached",
            operation_fenced=True,
            other_requests_pending=False,
            file_bound=False,
            context_proven=proof,
        )
        is not None
    )
    proof.assert_not_called()


@pytest.mark.parametrize("restriction", ["operation_fenced", "other_requests_pending", "file_bound"])
def test_independent_ownership_restrictions_cannot_be_overridden_by_portable_history(restriction):
    gates = dict(operation_fenced=True, other_requests_pending=False, file_bound=False)
    gates[restriction] = not gates[restriction]
    proof = Mock(side_effect=AssertionError("Ownership restriction must precede projection"))
    assert quota_handoff_rejection_reason(request(), "usage_limit_reached", **gates, context_proven=proof) is not None
    proof.assert_not_called()


@pytest.mark.parametrize(
    "code", [None, "stream_incomplete", "upstream_request_timeout", "server_is_overloaded", "server_error"]
)
def test_ambiguous_transport_errors_do_not_acquire_quota_recovery_permission(code):
    assert (
        quota_handoff_rejection_reason(
            request(),
            code,
            operation_fenced=True,
            other_requests_pending=False,
            file_bound=False,
            context_proven=lambda: True,
        )
        == "not_explicit_quota"
    )
