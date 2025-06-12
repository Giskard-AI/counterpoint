import datetime
import asyncio

import litellm
from pydantic import BaseModel, Field, PrivateAttr
from contextlib import nullcontext


class RateLimiterStrategy(BaseModel):
    rate_limiter_name: str = Field(default="global")
    max_concurrent_requests: int = Field(default=10)
    rate_limit_cooldown_interval: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=1)
    )
    max_limit_cooldown_interval: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=60)
    )


class RateLimiter(BaseModel):

    max_concurrent_requests: int = Field(default=10)
    rate_limit_cooldown_interval: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=1)
    )
    max_limit_cooldown_interval: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=60)
    )
    rate_limit_error_class: type[Exception] = Field(default=litellm.RateLimitError)

    _semaphore = PrivateAttr()
    _next_request_time: datetime.datetime | None = PrivateAttr()
    _current_cooldown_count: int = PrivateAttr()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self._next_request_time = None
        self._current_cooldown_count = 0

    async def acquire(self):
        await self._semaphore.acquire()

        if (
            self._next_request_time is not None
            and datetime.datetime.now() < self._next_request_time
        ):
            await asyncio.sleep(
                (self._next_request_time - datetime.datetime.now()).total_seconds()
            )

    async def release(self):
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.release()

        if exc_type is self.rate_limit_error_class:
            cooldown_interval = (
                self.rate_limit_cooldown_interval * 2**self._current_cooldown_count
            )
            self._next_request_time = datetime.datetime.now() + min(
                cooldown_interval, self.max_limit_cooldown_interval
            )
            self._current_cooldown_count += 1
        else:
            self._next_request_time = None
            self._current_cooldown_count = 0


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
