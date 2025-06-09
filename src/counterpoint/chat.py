from typing import Literal, Type, TypeVar

from litellm import Message as LiteLLMMessage
from pydantic import BaseModel

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
    content: str | Content | list[Content] = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    def to_litellm(self) -> dict:
        msg = self.model_dump(include={"role", "content", "tool_calls", "tool_call_id"})
        return msg

    @classmethod
    def from_litellm(cls, msg: LiteLLMMessage | dict):
        return cls(
            role=msg["role"],
            content=msg["content"],
            tool_calls=msg["tool_calls"],
        )

    def parse(self, model_type: Type[T]) -> T:
        return model_type.model_validate_json(self.content)


class Chat(BaseModel):
    messages: list[Message]

    @property
    def last(self) -> Message:
        return self.messages[-1]

    @property
    def transcript(self) -> str:
        return "\n".join([f"[{m.role}]: {m.content}" for m in self.messages])
