"""Own SQLite driver work through cancellation and transaction checkin."""

from __future__ import annotations

import asyncio
import functools
import sqlite3
import weakref
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from sqlalchemy import Result, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.interfaces import ExecutionContext
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.util import await_only

from app.core.utils.shared_future import _await_result_deferring_cancellation

_P = ParamSpec("_P")
_T = TypeVar("_T")
_owned_tasks: set[asyncio.Task[Any]] = set()
_writer_scope: ContextVar[bool] = ContextVar("sqlite_writer_scope", default=False)
_gates: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[Path, asyncio.Lock]] = weakref.WeakKeyDictionary()


def _owned(
    method: Callable[Concatenate[AsyncSession, _P], Awaitable[_T]],
) -> Callable[Concatenate[AsyncSession, _P], Awaitable[_T]]:
    @functools.wraps(method)
    async def call(session: AsyncSession, *args: _P.args, **kwargs: _P.kwargs) -> _T:
        assert isinstance(session, OwnedSqliteSession)
        return await session._run_owned(lambda: method(session, *args, **kwargs))

    return call


class OwnedSqliteSession(AsyncSession):
    """Sequential driver ownership; cancellation is surfaced after cleanup."""

    _driver_owner: asyncio.Task[Any] | None = None

    async def _run_owned(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        caller = asyncio.current_task()
        assert caller is not None
        if self._driver_owner is caller:
            return await operation()
        if self._driver_owner is not None:
            raise InvalidRequestError("Concurrent use of one SQLite session is not supported")
        # Claim synchronously, before the first yield: two callers must not
        # both enqueue a driver task before either task starts.
        self._driver_owner = caller
        _owned_tasks.add(caller)

        async def run() -> tuple[_T | None, BaseException | None]:
            self._driver_owner = asyncio.current_task()
            try:
                return await operation(), None
            except BaseException as exc:
                # Preserve the cancellation marker even when the driver fails.
                return None, exc

        async def cleanup() -> None:
            self._driver_owner = asyncio.current_task()
            try:
                await AsyncSession.rollback(self)
            finally:
                await AsyncSession.close(self)

        try:
            (result, error), cancellation = await _await_result_deferring_cancellation(run())
            if cancellation is not None:
                # execute buffers RETURNING before returning. Closing the
                # buffered Result cannot enqueue further SQLite worker work.
                if isinstance(result, Result):
                    result.close()
                await _await_result_deferring_cancellation(cleanup())
                raise cancellation
            if error is not None:
                raise error
            return cast(_T, result)
        finally:
            self._driver_owner = None
            _owned_tasks.discard(caller)

    execute = _owned(AsyncSession.execute)
    scalar = _owned(AsyncSession.scalar)
    scalars = _owned(AsyncSession.scalars)
    get = _owned(AsyncSession.get)
    get_one = _owned(AsyncSession.get_one)
    refresh = _owned(AsyncSession.refresh)
    flush = _owned(AsyncSession.flush)
    commit = _owned(AsyncSession.commit)
    rollback = _owned(AsyncSession.rollback)
    close = _owned(AsyncSession.close)
    reset = _owned(AsyncSession.reset)
    delete = _owned(AsyncSession.delete)
    merge = _owned(AsyncSession.merge)
    run_sync = _owned(AsyncSession.run_sync)
    connection = _owned(AsyncSession.connection)

    def begin(self) -> AsyncSessionTransaction:
        return _OwnedSqliteTransaction(self)

    def begin_nested(self) -> AsyncSessionTransaction:
        return _OwnedSqliteTransaction(self, nested=True)


class _OwnedSqliteTransaction(AsyncSessionTransaction):
    async def start(self, is_ctxmanager: bool = False) -> _OwnedSqliteTransaction:
        assert isinstance(self.session, OwnedSqliteSession)
        start = super().start
        await self.session._run_owned(lambda: start(is_ctxmanager=is_ctxmanager))
        return self

    async def commit(self) -> None:
        assert isinstance(self.session, OwnedSqliteSession)
        await self.session._run_owned(super().commit)

    async def rollback(self) -> None:
        assert isinstance(self.session, OwnedSqliteSession)
        await self.session._run_owned(super().rollback)

    async def __aexit__(self, type_: Any, value: Any, traceback: Any) -> None:
        assert isinstance(self.session, OwnedSqliteSession)
        exit_ = super().__aexit__
        await self.session._run_owned(lambda: exit_(type_, value, traceback))


def install_sqlite_admission(engine: Engine, *, timeout: float) -> None:
    """Hold the shared writer gate until transaction cleanup and checkin."""
    assert engine.url.database is not None
    path = Path(engine.url.database).resolve()

    async def acquire() -> asyncio.Lock:
        gates = _gates.setdefault(asyncio.get_running_loop(), {})
        gate = gates.setdefault(path, asyncio.Lock())
        try:
            async with asyncio.timeout(timeout):
                await gate.acquire()
        except TimeoutError as exc:
            from app.db.sqlite_writer_health import record_sqlite_busy

            record_sqlite_busy(path)
            raise sqlite3.OperationalError("database is locked (local writer admission timeout)") from exc
        return gate

    @event.listens_for(engine, "before_cursor_execute")
    def before_write(
        connection: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        # SELECT/EXPLAIN and PRAGMA queries remain concurrent. WITH is admitted
        # conservatively: SQLite supports WITH-prefixed writes as well as reads.
        operation = statement.lstrip().split(None, 1)[0].upper()
        if operation in {"SELECT", "EXPLAIN", "PRAGMA"} and not _writer_scope.get():
            return
        if "sqlite_admission_gate" not in connection.info:
            connection.info["sqlite_admission_gate"] = await_only(acquire())

    @event.listens_for(engine, "checkin")
    def after_cleanup(connection: Any, record: ConnectionPoolEntry) -> None:
        gate = record.info.pop("sqlite_admission_gate", None)
        if gate is not None:
            gate.release()


@asynccontextmanager
async def sqlite_writer_scope() -> AsyncIterator[None]:
    # This flag changes admission at the first statement, including reads that
    # guard a mutation. Each connection still claims the gate independently;
    # inheriting a context in another task never grants lock reentrancy.
    token = _writer_scope.set(True)
    try:
        yield
    finally:
        _writer_scope.reset(token)


async def drain_sqlite_operations(timeout: float) -> bool:
    if not _owned_tasks:
        return True
    _, pending = await asyncio.wait(tuple(_owned_tasks), timeout=timeout)
    return not pending
