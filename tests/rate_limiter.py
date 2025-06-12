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

async def mock__long_job(rate_limiter: RateLimiter):
    async with rate_limiter:
        started = time.monotonic()
        await asyncio.sleep(1)
        return started

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
        assert time.monotonic() - start_time >= throttle * i and time.monotonic() - start_time < throttle * (i + 1)
    
    # No throttle should be applied
    await asyncio.sleep(throttle)
    start_time = time.monotonic()
    async with rate_limiter:
        pass
    assert time.monotonic() - start_time < throttle


async def test_rate_limiter_burst_size():
    rate_limiter = RateLimiter(burst_size=10)
    throttle = 1 / 500

    tasks = [asyncio.create_task(mock__long_job(rate_limiter)) for _ in range(20)]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # First 10 requests should be run in burst
    first_start = results[0]
    for i in range(10):
        assert results[i] - first_start >= throttle * i and results[i] - first_start < throttle * (i + 1)

    # Last 10 requests should wait first task to finish
    second_burst_start = results[10]
    assert second_burst_start - first_start >= 1 and second_burst_start - first_start < 1 + throttle
    for i in range(10, 20):
        assert results[i] - second_burst_start >= throttle * (i - 10) and results[i] - second_burst_start < throttle * (i - 9)
