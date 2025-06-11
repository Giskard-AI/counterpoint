"""Core tool functionality for Counterpoint."""

import inspect
from typing import Any, Callable, Literal, TypeVar

from pydantic import BaseModel, create_model, Field

from ._docstring_parser import parse_docstring

F = TypeVar("F", bound=Callable[..., Any])


class Function(BaseModel):
    """Represents a function call in a tool call."""

    arguments: str
    name: str | None


class ToolCall(BaseModel):
    """Represents a tool call from the LLM."""

    id: str
    type: Literal["function"] = "function"
    function: Function


class Tool(BaseModel):
    """A tool that can be used with LLM completions."""

    name: str
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    fn: Callable

    @classmethod
    def from_callable(cls, fn: Callable) -> "Tool":
        """Create a Tool from a callable function.

        Parameters
        ----------
        fn : Callable
            The function to convert to a tool.

        Returns
        -------
        Tool
            A Tool instance.

        Raises
        ------
        ValueError
            If the function lacks proper annotations or docstring.
        """
        sig = inspect.signature(fn)

        description, parameter_descriptions = parse_docstring(fn, sig)

        fields = {}
        for name, param in sig.parameters.items():
            if param.annotation is inspect.Parameter.empty:
                raise ValueError(
                    f"Tool `{fn.__name__}` parameter `{name}` must have a type annotation"
                )

            field = Field(
                default=(
                    param.default
                    if param.default is not inspect.Parameter.empty
                    else ...
                ),
                description=parameter_descriptions.get(name, None),
            )

            fields[name] = (param.annotation, field)

        model = create_model(
            fn.__name__,
            **fields,
        )

        return cls(
            name=fn.__name__,
            description=description,
            parameters_schema=model.model_json_schema(),
            fn=fn,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the tool's function.

        This makes the Tool instance callable, so it can be used like a function.
        Handles both sync and async functions.

        Parameters
        ----------
        *args : Any
            Positional arguments to pass to the function.
        **kwargs : Any
            Keyword arguments to pass to the function.

        Returns
        -------
        Any
            The result of calling the function.
        """
        return self.fn(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool's function asynchronously.

        This method handles both sync and async functions by awaiting
        async functions and running sync functions in the current thread.

        Parameters
        ----------
        *args : Any
            Positional arguments to pass to the function.
        **kwargs : Any
            Keyword arguments to pass to the function.

        Returns
        -------
        Any
            The result of calling the function.
        """
        res = self.fn(*args, **kwargs)
        if inspect.isawaitable(res):
            res = await res

        if isinstance(res, BaseModel):
            res = res.model_dump()

        return res

    def to_litellm_function(self) -> dict[str, Any]:
        """Convert the tool to a LiteLLM function format.

        Returns
        -------
        dict[str, Any]
            A dictionary in the LiteLLM function format.
        """
        # Create the parameters object
        parameters = {
            "type": "object",
            "properties": {},
        }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


def tool(func: F) -> Tool:
    """Decorator to create a tool from a function.

    The function should have type annotations and a docstring in numpy or Google format.
    The docstring should describe the function and its parameters.

    Parameters
    ----------
    func : F
        The function to convert to a tool.

    Returns
    -------
    Tool
        A Tool instance that can be called like the original function.
    """
    return Tool.from_callable(func)
