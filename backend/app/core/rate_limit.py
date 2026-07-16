from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class CounterStore(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> object: ...


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class FixedWindowRateLimiter:
    def __init__(self, store: CounterStore, *, namespace: str = "rate-limit") -> None:
        self._store = store
        self._namespace = namespace

    async def check(
        self, *, scope: str, subject: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("rate limit and window must be positive")
        digest = hashlib.sha256(subject.encode()).hexdigest()
        key = f"{self._namespace}:{scope}:{digest}"
        count = await self._store.incr(key)
        if count == 1:
            await self._store.expire(key, window_seconds)
        return RateLimitResult(allowed=count <= limit, retry_after_seconds=window_seconds)
