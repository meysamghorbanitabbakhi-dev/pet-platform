from app.core.rate_limit import FixedWindowRateLimiter


class FakeCounterStore:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> object:
        self.expiries[key] = seconds
        return True


async def test_fixed_window_limit_and_hashed_subject() -> None:
    store = FakeCounterStore()
    limiter = FixedWindowRateLimiter(store)

    first = await limiter.check(
        scope="otp-mobile", subject="+989121234567", limit=2, window_seconds=600
    )
    second = await limiter.check(
        scope="otp-mobile", subject="+989121234567", limit=2, window_seconds=600
    )
    third = await limiter.check(
        scope="otp-mobile", subject="+989121234567", limit=2, window_seconds=600
    )

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    key = next(iter(store.values))
    assert "+989121234567" not in key
    assert store.expiries[key] == 600
