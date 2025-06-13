from typing import Literal, Type, TypeVar

from litellm import Message as LiteLLMMessage
from pydantic import BaseModel, Field

from counterpoint.context import RunContext
from counterpoint.tools import ToolCall

Role = Literal["assistant", "user", "system", "tool"]


class TextContent(BaseModel):
    type: Literal["text"] = "text"


class File(BaseModel):
    data: bytes


class FileContent(BaseModel):
    type: Literal["file"] = "file"
    file: File


class ThinkingContent(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str


Content = TextContent | ThinkingContent | None


T = TypeVar("T", bound=BaseModel)


class Message(BaseModel):
    role: Role
    content: str | Content | list[Content] | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    def to_litellm(self) -> dict:
        msg = self.model_dump(include={"role", "content", "tool_calls", "tool_call_id"})
        return msg

    @classmethod
    def from_litellm(cls, msg: LiteLLMMessage | dict):
        return cls.model_validate(msg.model_dump())

    def parse(self, model_type: Type[T]) -> T:
        return model_type.model_validate_json(self.content)


class Chat(BaseModel):
    messages: list[Message]
    output_model: Type[T] | None = None
    context: RunContext = Field(default_factory=RunContext)

    @property
    def last(self) -> Message:
        return self.messages[-1]

    @property
    def transcript(self) -> str:
        return "\n".join([f"[{m.role}]: {m.content}" for m in self.messages])

    @property
    def output(self) -> T:
        if self.output_model is None:
            raise ValueError("Output model not set")
        return self.last.parse(self.output_model)
