from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from threading import Lock
from time import monotonic


DEFAULT_PROVIDER_RPM = 6
MAX_PROVIDER_RPM = 60
_CANONICAL_DECIMAL = re.compile(r"^(0|[1-9][0-9]*)$")

AsyncSleeper = Callable[[float], Awaitable[None]]


def provider_rpm_from_environment(environment: Mapping[str, str]) -> int:
    raw = environment.get("RECALL_PROVIDER_RPM")
    if raw is None:
        return DEFAULT_PROVIDER_RPM
    if not _CANONICAL_DECIMAL.fullmatch(raw):
        raise RuntimeError("provider_rpm_invalid")
    value = int(raw)
    if not 1 <= value <= MAX_PROVIDER_RPM:
        raise RuntimeError("provider_rpm_invalid")
    return value


class ProviderRateLimiter:
    """One process-local fixed-interval limiter shared by all cohort roles."""

    def __init__(
        self,
        rpm: int,
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: AsyncSleeper = asyncio.sleep,
    ) -> None:
        if not 1 <= rpm <= MAX_PROVIDER_RPM:
            raise ValueError("provider_rpm_invalid")
        self._interval_seconds = 60.0 / rpm
        self._clock = clock
        self._sleeper = sleeper
        self._lock = Lock()
        self._next_dispatch_at: float | None = None
        self._dispatch_count = 0

    @property
    def dispatch_count(self) -> int:
        return self._dispatch_count

    async def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            slot = now if self._next_dispatch_at is None else max(
                now, self._next_dispatch_at
            )
            self._next_dispatch_at = slot + self._interval_seconds
            self._dispatch_count += 1
        wait_seconds = slot - now
        if wait_seconds > 0:
            await self._sleeper(wait_seconds)
