import time
from unittest.mock import patch

import pytest
from litellm import ModelResponse

from counterpoint.chat import Chat, Message
from counterpoint.generators.base import Response
from counterpoint.generators.litellm_generator import LiteLLMGenerator
from counterpoint.pipeline import Pipeline
from counterpoint.rate_limiter import RateLimiter
from counterpoint.templates import MessageTemplate


@pytest.fixture
def mock_response():
    return ModelResponse(
        choices=[
            dict(
                finish_reason="stop",
                message=dict(role="assistant", content="Mock response"),
            )
        ]
    )


async def test_litellm_generator_completion_with_mock(
    generator: LiteLLMGenerator, mock_response
):
    with patch(
        "counterpoint.generators.litellm_generator.acompletion",
        return_value=mock_response,
    ):
        response = await generator.complete(
            messages=[Message(role="user", content="Test message")]
        )

        assert response.message.role == "assistant"
        assert response.message.content == "Mock response"
        assert response.finish_reason == "stop"


async def test_generator_completion(generator: LiteLLMGenerator):
    response = await generator.complete(
        messages=[
            Message(
                role="system",
                content="You are a helpful assistant, greeting the user with 'Hello I am TestBot'.",
            ),
            Message(role="user", content="Hello, world!"),
        ]
    )

    assert isinstance(response, Response)
    assert response.message.role == "assistant"
    assert "I am TestBot" in response.message.content
    assert response.finish_reason == "stop"


async def test_generator_chat(generator: LiteLLMGenerator):
    test_message = "Hello, world!"
    pipeline = generator.chat(test_message)

    assert isinstance(pipeline, Pipeline)
    assert len(pipeline.messages) == 1
    assert isinstance(pipeline.messages[0], MessageTemplate)
    assert pipeline.messages[0].role == "user"
    assert pipeline.messages[0].content_template == test_message

    chat = await pipeline.run()

    assert isinstance(chat, Chat)

    chats = await pipeline.run_many(3)

    assert len(chats) == 3
    assert isinstance(chats[0], Chat)
    assert isinstance(chats[1], Chat)
    assert isinstance(chats[2], Chat)


async def test_litellm_generator_gets_rate_limiter(mock_response):
    rate_limiter = RateLimiter.from_rpm(rpm=60, max_concurrent=1)
    generator = LiteLLMGenerator(model="test-model", rate_limiter=rate_limiter)
    with patch(
        "counterpoint.generators.litellm_generator.acompletion",
        return_value=mock_response,
    ):
        start_time = time.monotonic()
        for _ in range(3):
            await generator.complete(
                messages=[Message(role="user", content="Test message")]
            )
        end_time = time.monotonic()

    # Distribution of request:
    # t = 0.0 -> request 1
    # t = 1.0 -> request 2
    # t = 2.0 -> request 3
    elapsed_time = end_time - start_time
    assert elapsed_time >= 2
    assert elapsed_time < 2 + rate_limiter.strategy.min_interval


async def test_generator_without_rate_limiter(mock_response):
    generator = LiteLLMGenerator(model="test-model")
    with patch(
        "counterpoint.generators.litellm_generator.acompletion",
        return_value=mock_response,
    ):
        start_time = time.monotonic()
        for _ in range(3):
            await generator.complete(
                messages=[Message(role="user", content="Test message")]
            )
        end_time = time.monotonic()

    elapsed_time = end_time - start_time
    assert elapsed_time < 10e-3  # arbitrary small number, here 10ms


async def test_generator_rate_limiter_context():
    rate_limiter = RateLimiter.from_rpm(rpm=100, rate_limiter_id="test")
    generator = LiteLLMGenerator(model="test-model", rate_limiter="test")
    assert generator.rate_limiter is rate_limiter


def test_generator_with_params():
    generator = LiteLLMGenerator(model="test-model")
    generator = generator.with_params(temperature=0.5)
    assert generator.params.temperature == 0.5

    new_generator = generator.with_params(temperature=0.7)
    assert new_generator.params.temperature == 0.7
    assert generator.params.temperature == 0.5

    int_generator = new_generator.with_params(response_format=int)
    assert int_generator.params.response_format is int
    assert new_generator.params.response_format is None
    assert generator.params.response_format is None
