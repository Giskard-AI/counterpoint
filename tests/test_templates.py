import pytest
from pathlib import Path
from counterpoint.templates import MessageTemplate
from counterpoint.templates.prompts_manager import PromptsManager


@pytest.fixture
def prompts_manager():
    return PromptsManager(prompts_path=Path(__file__).parent / "data" / "prompts")


async def test_message_template():
    template = MessageTemplate(
        role="user",
        content_template="Hello, {{ name }}!",
    )

    message = template.render(name="Orlande de Lassus")

    assert message.role == "user"
    assert message.content == "Hello, Orlande de Lassus!"


async def test_multi_message_template_parsing(prompts_manager):
    messages = await prompts_manager.render_template(
        "multi_message.j2",
        {
            "theory": "Normandy is actually the center of the universe because its perfect balance of rain, cheese, and cider creates a quantum field that bends space-time."
        },
    )

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert (
        "You are an impartial evaluator of scientific theories" in messages[0].content
    )


async def test_invalid_template(prompts_manager):
    with pytest.raises(ValueError):
        await prompts_manager.render_template("invalid.j2")


async def test_simple_template(prompts_manager):
    messages = await prompts_manager.render_template("simple.j2")

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert (
        messages[0].content
        == "This is a simple prompt that should be rendered as a single user message."
    )
