from counterpoint.rate_limiter import RateLimiter
import datetime
import asyncio
import pytest
import time


class MockRateLimitError(Exception):
    pass


async def mock_job(rate_limiter: RateLimiter):
    async with rate_limiter:
        return datetime.datetime.now()


async def test_rate_limiter_max_concurrent_requests():
    rate_limiter = RateLimiter()

    # Lock all threads
    for _ in range(10):
        await rate_limiter.acquire()

    # Create a task
    task = asyncio.create_task(mock_job(rate_limiter))

    # Task should be blocked
    assert not task.done()

    # Unlock a thread
    unlock_time = datetime.datetime.now()
    rate_limiter.release()

    # Task should be released
    await asyncio.wait_for(task, timeout=1.0)
    assert task.done()
    assert task.result() > unlock_time


async def test_rate_limiter_throttle_rate():
    rate_limiter = RateLimiter()

    throttle = 1 / 500
    start_time = time.monotonic()
    for i in range(10):
        async with rate_limiter:
            pass
        assert time.monotonic() - start_time > throttle * i and time.monotonic() - start_time < throttle * (i + 1)
    
    # No throttle should be applied
    await asyncio.sleep(throttle)
    start_time = time.monotonic()
    async with rate_limiter:
        pass
    assert time.monotonic() - start_time < throttle
