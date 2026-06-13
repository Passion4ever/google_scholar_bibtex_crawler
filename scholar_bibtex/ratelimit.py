import asyncio
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    """可重试的临时错误(超时、429、5xx 等)。"""


class RateLimiter:
    """信号量限并发 + 可选最小请求间隔。"""

    def __init__(self, concurrency: int = 3, min_interval: float = 0.0):
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self):
        await self._sem.acquire()
        if self._min_interval > 0:
            async with self._lock:
                now = time.monotonic()
                wait = self._last + self._min_interval - now
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = time.monotonic()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()
        return False


async def with_retry(
    factory: Callable[[], Awaitable[T]],
    retries: int = 3,
    base: float = 0.5,
) -> T:
    """对返回 awaitable 的工厂做指数退避重试,仅捕获 TransientError。"""
    last = None
    for attempt in range(retries):
        try:
            return await factory()
        except TransientError as e:
            last = e
            if attempt == retries - 1:
                raise
            await asyncio.sleep(base * (2 ** attempt))
    assert last is not None
    raise last
