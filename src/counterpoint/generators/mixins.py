from contextlib import nullcontext
from typing import AsyncContextManager

from pydantic import BaseModel, Field, field_validator

from ..rate_limiter import RateLimiter, get_rate_limiter


class WithRateLimiter(BaseModel):
    """Adds a rate limiter to the generator."""

    rate_limiter: RateLimiter | None = Field(default=None, validate_default=True)

    @field_validator("rate_limiter", mode="before")
    def _validate_rate_limiter(cls, v: RateLimiter | str | None) -> RateLimiter | None:
        if isinstance(v, str):
            v = get_rate_limiter(v)
        return v

    def _rate_limiter_context(self) -> AsyncContextManager:
        if self.rate_limiter is None:
            return nullcontext()

        return self.rate_limiter.throttle()
