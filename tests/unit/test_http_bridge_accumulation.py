from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.modules.proxy import http_bridge_event_batcher as module
from app.modules.proxy.http_bridge_event_batcher import HttpBridgeOperationEventBatcher

pytestmark = pytest.mark.unit


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.finalized: list[str] = []
        self.started = asyncio.Event()
        self.block = False

    async def append_operation_events(self, *, events, max_bytes: int) -> bool:
        self.started.set()
        if self.block:
            await asyncio.Future()
        self.batches.append([event.event_text for event in events])
        return True

    append_operation_event_chunk = append_operation_events

    async def finalize_operation_event_spool(self, *, operation_id: str, **kwargs) -> bool:
        self.finalized.append(operation_id)
        return True


async def enqueue(batcher: HttpBridgeOperationEventBatcher, text: str, operation: str = "one", **kwargs) -> None:
    await batcher.enqueue(
        operation_id=operation, session_id="session", instance_id="instance", owner_epoch=1, event_text=text, **kwargs
    )


async def settle() -> None:
    # Let wake/wait-for callbacks and the worker run, without wall-clock sleeps.
    for _ in range(20):
        await asyncio.sleep(0)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    value = SimpleNamespace(now=100.0)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: value.now))
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize("spool_format", ["rows_v1", "chunks_v2"])
async def test_paced_arrivals_keep_the_oldest_deadline(clock, spool_format: str) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(
        recorder, max_bytes=1024, batch_size=8, flush_interval_seconds=1, spool_format=spool_format
    )
    try:
        await enqueue(batcher, "first")
        await settle()
        assert recorder.batches == []
        clock.now = 100.75
        await enqueue(batcher, "second")
        await settle()
        assert recorder.batches == []
        clock.now = 101.0
        await enqueue(batcher, "third")
        await settle()
        assert recorder.batches == [["first", "second", "third"]]
        assert recorder.finalized == []
    finally:
        await batcher.close()


@pytest.mark.asyncio
async def test_threshold_flushes_before_deadline_and_remainder_keeps_its_age(clock) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(recorder, max_bytes=1024, batch_size=2, flush_interval_seconds=1)
    try:
        await enqueue(batcher, "first")
        clock.now = 100.25
        await enqueue(batcher, "second")
        await enqueue(batcher, "remainder")
        await settle()
        assert recorder.batches == [["first", "second"]]
        clock.now = 101.25
        await enqueue(batcher, "wake", operation="other")
        await settle()
        assert recorder.batches == [["first", "second"], ["remainder"]]
    finally:
        await batcher.close()


@pytest.mark.asyncio
async def test_terminal_drain_bypasses_deadline(clock) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(recorder, max_bytes=1024, flush_interval_seconds=60)
    try:
        await enqueue(batcher, "first")
        await settle()
        await enqueue(batcher, "terminal", terminal=True)
        assert recorder.batches == [["first", "terminal"]]
        assert recorder.finalized == ["one"]
    finally:
        await batcher.close()


@pytest.mark.asyncio
async def test_each_ready_operation_receives_one_batch_per_pass(clock) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(recorder, max_bytes=1024, batch_size=2, flush_interval_seconds=60)
    try:
        for text in ("busy1", "busy2", "busy3", "busy4"):
            await enqueue(batcher, text)
        await enqueue(batcher, "quiet1", operation="quiet")
        await enqueue(batcher, "quiet2", operation="quiet")
        await settle()
        assert recorder.batches == [["busy1", "busy2"], ["quiet1", "quiet2"], ["busy3", "busy4"]]
    finally:
        await batcher.close()


@pytest.mark.asyncio
async def test_background_rechecks_queue_replaced_during_flush_lock_wait(clock) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(recorder, max_bytes=1024, batch_size=2, flush_interval_seconds=60)
    try:
        await batcher._flush_lock.acquire()
        await enqueue(batcher, "old1")
        await enqueue(batcher, "old2")
        await settle()
        # A separate explicit drain consumes the selected queue first. The
        # stale background selection must not write its replacement early.
        await batcher._take_batch("one")
        await enqueue(batcher, "new")
        batcher._flush_lock.release()
        await settle()
        assert recorder.batches == []
        await batcher.flush_pending_operation(operation_id="one")
        assert recorder.batches == [["new"]]
    finally:
        if batcher._flush_lock.locked():
            batcher._flush_lock.release()
        await batcher.close()


@pytest.mark.asyncio
async def test_cancelled_background_append_cannot_finalize_a_missing_batch() -> None:
    recorder = Recorder()
    recorder.block = True
    batcher = HttpBridgeOperationEventBatcher(recorder, max_bytes=1024, batch_size=1, flush_interval_seconds=60)
    try:
        await enqueue(batcher, "lost")
        await asyncio.wait_for(recorder.started.wait(), 1)
        await batcher.close()
        recorder.block = False
        await enqueue(batcher, "terminal", terminal=True)
        assert recorder.batches == []
        assert recorder.finalized == []
    finally:
        await batcher.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("spool_format", ["rows_v1", "chunks_v2"])
async def test_overflow_during_accumulation_does_not_finalize_partial_transcript(clock, spool_format: str) -> None:
    recorder = Recorder()
    batcher = HttpBridgeOperationEventBatcher(
        recorder, max_bytes=1024, max_pending_events=2, flush_interval_seconds=60, spool_format=spool_format
    )
    try:
        await enqueue(batcher, "one")
        await enqueue(batcher, "two")
        await enqueue(batcher, "overflow")
        await enqueue(batcher, "terminal", terminal=True)
        assert recorder.batches == []
        assert recorder.finalized == []
        assert await batcher.pending_operation_ids() == set()
    finally:
        await batcher.close()
