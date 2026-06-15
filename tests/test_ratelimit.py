import asyncio
import time

import pytest

from scholar_bibtex.ratelimit import RateLimiter, with_retry, TransientError


async def test_concurrency_cap_enforced():
    limiter = RateLimiter(concurrency=2)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with limiter:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*[worker() for _ in range(6)])
    assert peak <= 2


async def test_min_interval_spaces_requests():
    limiter = RateLimiter(concurrency=5, min_interval=0.05)
    start = time.monotonic()

    async def worker():
        async with limiter:
            pass

    await asyncio.gather(*[worker() for _ in range(3)])
    elapsed = time.monotonic() - start
    # 3 次至少间隔 2 个 min_interval
    assert elapsed >= 0.09


async def test_with_retry_succeeds_after_transient():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("boom")
        return "ok"

    result = await with_retry(flaky, retries=3, base=0.001)
    assert result == "ok"
    assert calls["n"] == 3


async def test_with_retry_reraises_after_exhaustion():
    async def always_fail():
        raise TransientError("nope")

    with pytest.raises(TransientError):
        await with_retry(always_fail, retries=2, base=0.001)
