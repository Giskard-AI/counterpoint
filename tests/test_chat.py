import pytest
from pydantic import BaseModel

from counterpoint.chat import Chat, Message
from counterpoint.exceptions import CounterpointConfigError


def test_chat_output():
    """Test that Message.parse correctly parses JSON content to a Pydantic model."""

    class Cheese(BaseModel):
        name: str
        region: str

    messages = [
        Message(role="user", content="What is the best cheese? Answer in JSON."),
        Message(
            role="assistant", content='{"name": "Camembert", "region": "Normandy"}'
        ),
    ]

    chat = Chat(messages=messages, output_model=Cheese)

    assert isinstance(chat.output, Cheese)
    assert chat.output == Cheese(name="Camembert", region="Normandy")


def test_chat_output_without_output_model():
    messages = [
        Message(role="user", content="What is the best cheese? Answer in JSON."),
        Message(
            role="assistant", content='{"name": "Camembert", "region": "Normandy"}'
        ),
    ]

    chat = Chat(messages=messages)
    with pytest.raises(CounterpointConfigError):
        chat.output
