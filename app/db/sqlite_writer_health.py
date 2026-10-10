"""Check write capability only after sustained SQLite busy failures."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.db.sqlite_utils import sqlite_db_path_from_url, sqlite_url_is_memory

logger = logging.getLogger(__name__)

_FAILURE_WINDOW_SECONDS = 30.0
_PROBE_INTERVAL_SECONDS = 30.0
_PROBE_BUSY_TIMEOUT_SECONDS = 0.25
_PROBE_WAIT_SECONDS = 1.0


@dataclass
class _WriterState:
    first_busy_at: float | None = None
    last_busy_at: float = 0.0
    busy_count: int = 0
    unavailable: bool = False
    last_probe_at: float = float("-inf")
    probe_task: asyncio.Task[bool] | None = None


_states: dict[Path, _WriterState] = {}
_state_lock = threading.Lock()


def record_sqlite_busy(path: Path) -> None:
    now = time.monotonic()
    with _state_lock:
        state = _states.setdefault(path.resolve(), _WriterState())
        if state.first_busy_at is None or now - state.last_busy_at > 2 * _FAILURE_WINDOW_SECONDS:
            state.first_busy_at = now
            state.busy_count = 0
        state.last_busy_at = now
        state.busy_count += 1


def record_sqlite_write_success(path: Path) -> None:
    with _state_lock:
        state = _states.get(path.resolve())
        if state is not None:
            state.first_busy_at = None
            state.busy_count = 0
            state.unavailable = False


def _probe_writer_slot(path: Path) -> bool:
    # mode=rw prevents a readiness request from creating a missing database.
    try:
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw",
            uri=True,
            timeout=_PROBE_BUSY_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("ROLLBACK")
        finally:
            connection.close()
    except sqlite3.Error as exc:
        code = getattr(exc, "sqlite_errorcode", None)
        is_busy = code is not None and code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
        logger.warning(
            "%s database=%s error_type=%s sqlite_errorcode=%s; acquisition failure does not identify a lock owner",
            "sqlite_writer_slot_held" if is_busy else "sqlite_writer_probe_failed",
            path,
            type(exc).__name__,
            code,
        )
        return False
    return True


def _probe_done(state: _WriterState, task: asyncio.Task[bool]) -> None:
    try:
        ready = task.result()
    except BaseException:
        ready = False
        logger.warning("SQLite writer readiness probe did not complete successfully", exc_info=True)
    with _state_lock:
        state.unavailable = not ready
        if ready:
            state.first_busy_at = None
            state.busy_count = 0
        state.probe_task = None


async def sqlite_writer_is_ready(database_url: str) -> bool:
    path = sqlite_db_path_from_url(database_url)
    if path is None or sqlite_url_is_memory(database_url):
        return True
    path = path.resolve()
    now = time.monotonic()
    with _state_lock:
        state = _states.get(path)
        if state is None:
            return True
        task = state.probe_task
        sustained = (
            state.first_busy_at is not None
            and state.busy_count >= 2
            and now - state.first_busy_at >= _FAILURE_WINDOW_SECONDS
        )
        if task is None:
            if not (state.unavailable or sustained):
                return True
            if now - state.last_probe_at < _PROBE_INTERVAL_SECONDS:
                return not state.unavailable
            state.last_probe_at = now
            task = asyncio.create_task(asyncio.to_thread(_probe_writer_slot, path), name="sqlite-writer-readiness")
            state.probe_task = task
            task.add_done_callback(lambda finished: _probe_done(state, finished))
    # asyncio.wait observes without cancelling the owned worker on timeout or
    # caller cancellation. The worker always rolls back/closes its connection.
    done, _ = await asyncio.wait({task}, timeout=_PROBE_WAIT_SECONDS)
    if task not in done:
        return False
    try:
        return task.result()
    except Exception:
        return False
