import datetime
import asyncio
import time

from pydantic import BaseModel, Field, PrivateAttr
from contextlib import nullcontext


class RateLimiterStrategy(BaseModel):
    rate_limiter_name: str = Field(default="global")
    rpm: int = Field(default=500)
    burst_size: int = Field(default=10)

class RateLimiter(BaseModel):
    rpm: int = Field(default=500)
    tpm: int = Field(default=30000)
    burst_size: int = Field(default=10)
    
    _semaphore: asyncio.Semaphore = PrivateAttr()
    _next_request_time: float = PrivateAttr(default=time.monotonic())
    _lock: asyncio.Lock = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._semaphore = asyncio.Semaphore(self.burst_size)
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self._semaphore.acquire()
        
        # Lock to avoid concurrent access of next_request_time making the throttle rate not respected
        async with self._lock:
            now = time.monotonic()
            if self._next_request_time > now:
                wait_time = self._next_request_time - now
                await asyncio.sleep(wait_time)
                self._next_request_time += (1 / self.rpm)
            else:
                self._next_request_time = now + (1 / self.rpm)

    def release(self):
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.release()


global_models_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(strategy: RateLimiterStrategy | None = None) -> RateLimiter:
    if strategy is None:
        return nullcontext()

    if strategy.rate_limiter_name not in global_models_rate_limiters:
        global_models_rate_limiters[strategy.rate_limiter_name] = RateLimiter(
            max_concurrent_requests=strategy.max_concurrent_requests,
            rate_limit_cooldown_interval=strategy.rate_limit_cooldown_interval,
            max_limit_cooldown_interval=strategy.max_limit_cooldown_interval,
        )
        
    return global_models_rate_limiters[strategy.rate_limiter_name]
