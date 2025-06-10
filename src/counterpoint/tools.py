import inspect
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field


class Function(BaseModel):
    arguments: str
    name: str | None


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: Function


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    fn: Callable

    @classmethod
    def from_callable(cls, fn: Callable) -> "Tool":
        return cls(
            name=fn.__name__,
            description=fn.__doc__,
            parameters=fn.__annotations__,
            fn=fn,
        )

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        res = self.fn(*args, **kwargs)
        if inspect.isawaitable(res):
            res = await res

        return res

    def to_litellm_function(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
