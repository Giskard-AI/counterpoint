import asyncio
from typing import TYPE_CHECKING, Literal

from litellm import acompletion
from pydantic import BaseModel, Field

from .chat import Message
from .tools.tool import Tool

if TYPE_CHECKING:
    from .pipeline import Pipeline


class GenerationParams(BaseModel):
    """Parameters for generating a completion.

    Attributes
    ----------
    tools : list[Any], optional
        List of tools available to the model.
    """

    temperature: float = Field(default=1.0)
    tools: list[Tool] = Field(default_factory=list)


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

    async def _complete(
        self, messages: list[Message], params: GenerationParams | None = None
    ) -> Response:
        params_ = {}

        if params:
            params_ = params.model_dump(exclude={"tools"})

        if params.tools:
            params_["tools"] = [t.to_litellm_function() for t in params.tools]

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

    async def complete(
        self, messages: list[Message], params: GenerationParams | None = None
    ) -> Response:
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
        return await self._complete(messages, params)

    async def batch_complete(
        self, messages: list[list[Message]], params: GenerationParams | None = None
    ) -> list[Response]:
        """Get a batch of completions from the model.

        Parameters
        ----------
        messages : List[List[Message]]
            List of lists of messages to send to the model.
        params : GenerationParams, optional
            Parameters for the generation.

        Returns
        -------
        list[Response]
            A list of model's responses.
        """
        completion_requests = [self._complete(m, params) for m in messages]
        responses = await asyncio.gather(*completion_requests)
        return responses

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
