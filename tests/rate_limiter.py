from counterpoint.rate_limiter import RateLimiter
import datetime
import asyncio
import pytest


class MockRateLimitError(Exception):
    pass


async def mock_job(rate_limiter: RateLimiter):
    async with rate_limiter:
        return datetime.datetime.now()


async def mock_job_with_error(rate_limiter: RateLimiter):
    async with rate_limiter:
        raise MockRateLimitError()


async def test_rate_limiter_acquire_release():
    rate_limiter = RateLimiter(
        rate_limit_error_class=MockRateLimitError,
    )

    # Lock all threads
    for _ in range(10):
        await rate_limiter.acquire()

    # Create a task
    task = asyncio.create_task(mock_job(rate_limiter))

    # Task should be blocked
    assert not task.done()

    # Unlock a thread
    unlock_time = datetime.datetime.now()
    await rate_limiter.release()

    # Task should be released
    await asyncio.wait_for(task, timeout=1.0)
    assert task.done()
    assert task.result() > unlock_time


async def test_rate_limiter_cooldown():
    rate_limiter = RateLimiter(
        rate_limit_error_class=MockRateLimitError,
    )

    # First error should trigger cooldown
    with pytest.raises(MockRateLimitError):
        start_time = datetime.datetime.now()
        await mock_job_with_error(rate_limiter)

    # Second error should trigger cooldown exponentially
    with pytest.raises(MockRateLimitError):
        start_time = datetime.datetime.now()
        await mock_job_with_error(rate_limiter)
        assert datetime.datetime.now() - start_time > datetime.timedelta(
            seconds=1
        ) and datetime.datetime.now() - start_time < datetime.timedelta(seconds=2)

    # No error should reset cooldown
    start_time = datetime.datetime.now()
    await mock_job(rate_limiter)
    assert datetime.datetime.now() - start_time > datetime.timedelta(
        seconds=2
    ) and datetime.datetime.now() - start_time < datetime.timedelta(seconds=3)

    start_time = datetime.datetime.now()
    await mock_job(rate_limiter)
    assert datetime.datetime.now() - start_time < datetime.timedelta(seconds=1)

    with pytest.raises(MockRateLimitError):
        start_time = datetime.datetime.now()
        await mock_job_with_error(rate_limiter)

    start_time = datetime.datetime.now()
    await mock_job(rate_limiter)
    assert datetime.datetime.now() - start_time > datetime.timedelta(
        seconds=1
    ) and datetime.datetime.now() - start_time < datetime.timedelta(seconds=2)


async def test_rate_limiter_cooldown_with_max_limit_cooldown_interval():
    rate_limiter = RateLimiter(
        rate_limit_error_class=MockRateLimitError,
        max_limit_cooldown_interval=datetime.timedelta(seconds=1),
    )

    # First error should trigger cooldown
    with pytest.raises(MockRateLimitError):
        start_time = datetime.datetime.now()
        await mock_job_with_error(rate_limiter)

    # Second error should reach max cooldown interval
    with pytest.raises(MockRateLimitError):
        start_time = datetime.datetime.now()
        await mock_job_with_error(rate_limiter)
        assert datetime.datetime.now() - start_time > datetime.timedelta(
            seconds=1
        ) and datetime.datetime.now() - start_time < datetime.timedelta(seconds=2)

    start_time = datetime.datetime.now()
    await mock_job(rate_limiter)
    assert datetime.datetime.now() - start_time > datetime.timedelta(
        seconds=1
    ) and datetime.datetime.now() - start_time < datetime.timedelta(seconds=2)
