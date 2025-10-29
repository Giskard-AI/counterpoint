from typing import Generic, Literal, Type, TypeVar

from litellm import Message as LiteLLMMessage
from pydantic import BaseModel, Field

from counterpoint.context import RunContext
from counterpoint.exceptions import CounterpointConfigError
from counterpoint.errors.serializable import Error
from counterpoint.tools import ToolCall

Role = Literal["assistant", "user", "system", "tool"]


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


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
OutputType = TypeVar("OutputType", bound=BaseModel)


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

    @property
    def transcript(self) -> str:
        role = self.role
        if role == "tool" and self.tool_call_id is not None:
            role += f":{self.tool_call_id}"

        content = str(self.content)
        if self.tool_calls:
            for tool_call in self.tool_calls:
                content += f"\n>[tool_call:{tool_call.function.name}:{tool_call.id}]: {tool_call.function.arguments}"

        return f"[{role}]: {content}"


class Chat(BaseModel, Generic[OutputType]):
    messages: list[Message]
    output_model: Type[OutputType] | None = Field(default=None)
    context: RunContext = Field(default_factory=RunContext)

    error: Error | None = None

    @property
    def last(self) -> Message:
        return self.messages[-1]

    @property
    def transcript(self) -> str:
        return "\n".join([m.transcript for m in self.messages])

    @property
    def output(self) -> OutputType:
        """Parsed output as the configured model.

        Raises
        ------
        CounterpointConfigError
            If no `output_model` is configured on the chat/pipeline.
        """
        if self.output_model is None:
            raise CounterpointConfigError(
                "Output model not set. Call Pipeline.with_output(...) before accessing Chat.output."
            )
        return self.last.parse(self.output_model)

    @property
    def failed(self) -> bool:
        return self.error is not None

    def clone(self, deep: bool = True) -> "Chat":
        return self.model_copy(deep=deep)

    def add(self, message: Message) -> "Chat":
        self.messages.append(message)
        return self
