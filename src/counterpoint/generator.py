from typing import TYPE_CHECKING, Any, List, Literal

from litellm import acompletion
from pydantic import BaseModel, Field

from .chat import Message

if TYPE_CHECKING:
    from .pipeline import Pipeline


class GenerationParams(BaseModel):
    """Parameters for generating a completion.

    Attributes
    ----------
    tools : List[Any], optional
        List of tools available to the model.
    """

    temperature: float = Field(default=1.0)
    tools: List[Any] = Field(default_factory=list)


class Response(BaseModel):
    message: Message
    finish_reason: Literal["stop", "length", "tool_calls"] | None


class Generator(BaseModel):
    """A generator for creating chat completion pipelines.

    Attributes
    ----------
    model : str
        The model identifier to use (e.g. 'gemini/gemini-2.0-flash').
    """

    model: str = Field(
        description="The model identifier to use (e.g. 'gemini/gemini-2.0-flash')"
    )

    async def complete(
        self, messages: List[Message], params: GenerationParams | None = None
    ) -> Message:
        """Get a completion from the model.

        Parameters
        ----------
        messages : List[Message]
            List of messages to send to the model.
        tools : List[Any], optional
            List of tools available to the model.

        Returns
        -------
        Message
            The model's response message.
        """
        params_ = {}

        if params:
            params_ = params.model_dump()

        response = await acompletion(
            messages=[m.to_litellm() for m in messages],
            model=self.model,
            **params_,
        )

        choice = response.choices[0]
        return Response(
            message=Message.from_litellm(choice.message),
            finish_reason=choice.finish_reason,
        )

    def chat(self, message: str) -> "Pipeline":
        """Create a new chat pipeline with the given message.

        Parameters
        ----------
        message : str
            The initial message to start the chat with.

        Returns
        -------
        Pipeline
            A Pipeline object that can be used to run the completion.
        """
        from .pipeline import Pipeline

        messages = [Message(role="user", content=message)]
        return Pipeline(generator=self, messages=messages, model=self.model)
