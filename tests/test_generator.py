from counterpoint.chat import Chat, Message
from counterpoint.generator import Generator, Message, Response
from counterpoint.pipeline import Pipeline
from counterpoint.templates import MessageTemplate


async def test_generator_completion(generator: Generator):

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


async def test_generator_chat(generator: Generator):

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
