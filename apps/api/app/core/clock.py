"""Injectable clock helper so sandbox 'Advance time' offsets work deterministically."""
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

ClockFn = Callable[[], datetime]


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


def make_clock(offset_hours: float = 0.0, base_clock: ClockFn = utc_now) -> ClockFn:
    """Return a clock function shifted forward by `offset_hours`."""
    delta = timedelta(hours=offset_hours)

    def _clock() -> datetime:
        return base_clock() + delta

    return _clock
