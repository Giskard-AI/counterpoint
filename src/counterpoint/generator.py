import asyncio
from contextlib import nullcontext
from typing import TYPE_CHECKING, AsyncContextManager, Literal

from litellm import acompletion
from pydantic import BaseModel, Field, field_validator

from .chat import Message, Role
from .rate_limiter import RateLimiter, get_rate_limiter
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
    """A generator for creating chat completion pipelines."""

    model: str = Field(
        description="The model identifier to use (e.g. 'gemini/gemini-2.0-flash')"
    )
    params: GenerationParams = Field(default_factory=GenerationParams)
    rate_limiter: RateLimiter | None = Field(default=None, validate_default=True)

    @field_validator("rate_limiter", mode="before")
    def _validate_rate_limiter(cls, v: RateLimiter | str | None) -> RateLimiter | None:
        if isinstance(v, str):
            return get_rate_limiter(v)
        return v

    async def _complete(
        self, messages: list[Message], params: GenerationParams | None = None
    ) -> Response:
        params_ = self.params.model_dump(exclude={"tools"})

        if params is not None:
            params_.update(params.model_dump(exclude={"tools"}))

        # Now special handling of the tools
        tools = self.params.tools + (params.tools if params is not None else [])
        if tools:
            params_["tools"] = [t.to_litellm_function() for t in tools]

        async with self._rate_limiter_context():
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

    def _rate_limiter_context(self) -> AsyncContextManager:
        if self.rate_limiter is None:
            return nullcontext()

        return self.rate_limiter.throttle()

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

    def chat(self, message: str, role: Role = "user") -> "Pipeline":
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

        return Pipeline(generator=self).chat(message, role)
