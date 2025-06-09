from typing import Literal

from pydantic import BaseModel


class Function(BaseModel):
    arguments: str
    name: str | None


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: Function
