from pydantic import BaseModel
from typing import Literal

Role = Literal["system", "user", "assistant", "tool", "developer"]


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


Content = TextContent | ThinkingContent


class Message(BaseModel):
    role: Role
    content: str | Content | list[Content]


class Chat(BaseModel):
    messages: list[Message]

    @property
    def last(self) -> Message:
        return self.messages[-1]

    @property
    def transcript(self) -> str:
        return "\n".join([f"[{m.role}]: {m.content}" for m in self.messages])
