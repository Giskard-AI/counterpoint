from litellm import acompletion
from pydantic import Field

from ..chat import Message
from .base import BaseGenerator, GenerationParams, Response
from .mixins import WithRateLimiter


class LiteLLMGenerator(WithRateLimiter, BaseGenerator):
    """A generator for creating chat completion pipelines."""

    model: str = Field(
        description="The model identifier to use (e.g. 'gemini/gemini-2.0-flash')"
    )

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
