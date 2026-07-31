from datetime import date
from pathlib import Path

import pytest

from google_health_agent.backfill import (
    BackfillLockedError,
    date_batches,
    exclusive_sync_lock,
    run_backfill,
)


def test_batches_cover_range_without_overlap() -> None:
    assert list(date_batches(date(2026, 1, 1), date(2026, 1, 8), 3)) == [
        (date(2026, 1, 1), date(2026, 1, 3)),
        (date(2026, 1, 4), date(2026, 1, 6)),
        (date(2026, 1, 7), date(2026, 1, 8)),
    ]


def test_backfill_checkpoints_after_success_and_resumes(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    attempted: list[date] = []

    def fail_second(start: date, _end: date) -> int:
        attempted.append(start)
        if len(attempted) == 2:
            raise RuntimeError("mock failure")
        return 4

    with pytest.raises(RuntimeError):
        run_backfill(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 6),
            batch_days=2,
            state_path=state_path,
            sync_batch=fail_second,
        )
    assert state_path.exists()
    assert (state_path.stat().st_mode & 0o777) == 0o600

    resumed: list[date] = []
    result = run_backfill(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 6),
        batch_days=2,
        state_path=state_path,
        sync_batch=lambda start, _end: resumed.append(start) or 5,
    )
    assert resumed == [date(2026, 1, 3), date(2026, 1, 5)]
    assert result.observations == 10
    assert not state_path.exists()


def test_sync_lock_rejects_concurrent_holder(tmp_path: Path) -> None:
    lock = tmp_path / "sync.lock"
    with exclusive_sync_lock(lock), pytest.raises(BackfillLockedError), exclusive_sync_lock(lock):
        pass
    assert (lock.stat().st_mode & 0o777) == 0o600
