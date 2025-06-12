import asyncio
import time

from pydantic import BaseModel, Field, PrivateAttr
from contextlib import nullcontext


class RateLimiterStrategy(BaseModel):
    limiter_id: str = Field(default="global")
    rpm: int = Field(default=500)
    burst_size: int = Field(default=10)


class RateLimiter(BaseModel):
    rpm: int = Field(default=500)
    burst_size: int = Field(default=10)

    _semaphore: asyncio.Semaphore = PrivateAttr()
    _next_request_time: float = PrivateAttr(default_factory=time.monotonic)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    def model_post_init(self, __context) -> None:
        self._semaphore = asyncio.Semaphore(self.burst_size)

    async def acquire(self):
        await self._semaphore.acquire()

        # Lock to avoid concurrent access of next_request_time making the throttle rate not respected
        async with self._lock:
            now = time.monotonic()
            if self._next_request_time > now:
                wait_time = self._next_request_time - now
                await asyncio.sleep(wait_time)
                self._next_request_time += 1 / self.rpm
            else:
                self._next_request_time = now + (1 / self.rpm)

    def release(self):
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.release()


_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(strategy: RateLimiterStrategy | None = None) -> RateLimiter:
    if strategy is None:
        return nullcontext()

    if strategy.limiter_id not in _rate_limiters:
        _rate_limiters[strategy.limiter_id] = RateLimiter(
            rpm=strategy.rpm,
            burst_size=strategy.burst_size,
        )

    return _rate_limiters[strategy.limiter_id]
