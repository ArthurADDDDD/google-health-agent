"""Private, resumable, idempotent history-backfill primitives."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile


class BackfillLockedError(RuntimeError):
    """Raised when another sync/backfill process owns the exclusive lock."""


@dataclass(frozen=True)
class BackfillProgress:
    batches: int
    observations: int


def date_batches(start_date: date, end_date: date, batch_days: int) -> Iterator[tuple[date, date]]:
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    if batch_days < 1 or batch_days > 90:
        raise ValueError("batch_days must be between 1 and 90")
    current = start_date
    while current <= end_date:
        batch_end = min(end_date, current + timedelta(days=batch_days - 1))
        yield current, batch_end
        current = batch_end + timedelta(days=1)


@contextmanager
def exclusive_sync_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackfillLockedError("Another Google Health sync is already running.") from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def run_backfill(
    *,
    start_date: date,
    end_date: date,
    batch_days: int,
    state_path: Path,
    sync_batch: Callable[[date, date], int],
) -> BackfillProgress:
    """Run sequential batches and checkpoint only after a successful database upsert."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = _load_state(state_path, start_date, end_date, batch_days)
    current = state or start_date
    completed = 0
    observations = 0
    for batch_start, batch_end in date_batches(current, end_date, batch_days):
        observations += sync_batch(batch_start, batch_end)
        completed += 1
        next_start = batch_end + timedelta(days=1)
        if next_start <= end_date:
            _write_state(state_path, start_date, end_date, batch_days, next_start)
        else:
            state_path.unlink(missing_ok=True)
    return BackfillProgress(batches=completed, observations=observations)


def _load_state(state_path: Path, start_date: date, end_date: date, batch_days: int) -> date | None:
    if not state_path.exists():
        return None
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        expected = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "batch_days": batch_days,
        }
        if {key: value.get(key) for key in expected} != expected:
            raise ValueError
        next_start = date.fromisoformat(str(value["next_start_date"]))
        if not start_date <= next_start <= end_date:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        message = "Backfill state is invalid or does not match this requested range."
        raise ValueError(message) from exc
    return next_start


def _write_state(
    state_path: Path, start_date: date, end_date: date, batch_days: int, next_start: date
) -> None:
    payload = json.dumps(
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "batch_days": batch_days,
            "next_start_date": next_start.isoformat(),
        },
        sort_keys=True,
    )
    with NamedTemporaryFile("w", encoding="utf-8", dir=state_path.parent, delete=False) as handle:
        os.chmod(handle.name, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(state_path)
    os.chmod(state_path, 0o600)
