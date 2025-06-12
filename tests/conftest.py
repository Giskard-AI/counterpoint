import os
import pytest
import counterpoint as cp


@pytest.fixture
async def generator():
    """Fixture providing a configured generator for tests."""
    return cp.Generator(model=os.getenv("TEST_MODEL", "gemini/gemini-2.0-flash"))
