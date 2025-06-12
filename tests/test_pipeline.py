import counterpoint as cp


async def test_single_run(generator):
    pipeline = cp.Pipeline(generator=generator)

    chat = await (
        pipeline.chat("Your name is TestBot.", role="system")
        .chat("What is your name? Answer in one word.", role="user")
        .run()
    )

    assert "testbot" in chat.last.content.lower()


async def test_run_many(generator):
    """Test that the pipeline runs correctly."""

    pipeline = cp.Pipeline(generator=generator)

    chats = await pipeline.chat("Hello!", role="user").run_many(n=3)

    assert len(chats) == 3


async def test_run_batch(generator):
    """Test that the pipeline runs correctly."""

    pipeline = cp.Pipeline(generator=generator)

    chats = await pipeline.chat("Hello!", role="user").run_batch(
        inputs=[{"message": "Hello!"} for _ in range(3)]
    )

    assert len(chats) == 3
