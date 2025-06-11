import asyncio
import json
from typing import AsyncGenerator, Dict, List, Type, Any, Optional

from pydantic import BaseModel, Field

from counterpoint.chat import Chat, Message
from counterpoint.generator import GenerationParams, Generator
from counterpoint.tools.tool import Tool


class PipelineStep(BaseModel):
    """A step in a pipeline."""

    pipeline: "Pipeline"
    chats: List[Chat]
    previous: Optional["PipelineStep"] = Field(default=None)


StepGenerator = AsyncGenerator[PipelineStep, None]


class Pipeline(BaseModel):
    """A pipeline for handling chat completions.

    Attributes
    ----------
    messages : List[Message]
        List of chat messages in the conversation.
    model : str
        The model identifier to use for completions.
    tools : List[Any]
        List of tools available to the pipeline.
    generator : Generator
        The generator instance to use for completions.
    """

    messages: List[Message] = Field(default_factory=list)
    model: str
    tools: Dict[str, Tool] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    generator: "Generator"
    output_model: Type[BaseModel] = None

    def with_tools(self, *tools: Tool):
        """Add tools to the pipeline.

        Parameters
        ----------
        *tools : Tool
            Tools to add to the pipeline.

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        for tool in tools:
            self.tools[tool.name] = tool
        return self

    def with_output(self, output_model: Type[BaseModel]):
        """Set the output model for the pipeline.

        Parameters
        ----------
        output_model : Type[BaseModel]
            The output model to use for the pipeline.

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        self.output_model = output_model
        return self

    def with_inputs(self, **kwargs: Any) -> "Pipeline":
        """Set the input for the pipeline.

        Parameters
        ----------
        **kwargs : Any
            The input for the pipeline.

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        self.inputs.update(kwargs)
        return self

    async def _run_steps(self, steps: int | None = None) -> StepGenerator:
        params = GenerationParams(
            tools=list(self.tools.values()),
        )

        current_step = None
        current_step_num = 0
        current_chat = Chat(
            messages=self.messages,
            output_model=self.output_model,
        )
        while True:
            if steps is not None and current_step_num >= steps:
                break

            response = await self.generator.complete(current_chat.messages, params)

            current_step_num += 1
            current_chat = Chat(
                messages=current_chat.messages + [response.message],
                output_model=self.output_model,
            )

            current_step = PipelineStep(
                pipeline=self,
                chats=[current_chat],
                previous=current_step,
            )

            yield current_step

            # If the last message is a tool call, we will run the tools and add
            # the results to the chat.
            if current_chat.last.tool_calls:
                tool_messages = []
                for tool_call in current_chat.last.tool_calls:
                    tool = self.tools[tool_call.function.name]
                    tool_response = await tool.run(**json.loads(tool_call.function.arguments))
                    tool_messages.append(
                        Message(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=json.dumps(tool_response),
                        )
                    )
                current_chat = Chat(
                    messages=current_chat.messages + tool_messages,
                    output_model=self.output_model,
                )
            else:
                # All done, no tool calls, we stop here.
                return

    async def run(self, steps: int | None = None) -> Chat:
        """Runs the pipeline.

        Parameters
        ----------
        steps : int, optional
            The number of steps to run. If not provided, the pipeline will run until the chat is complete.

        Returns
        -------
        Chat
            A Chat object containing the conversation messages.
        """
        step = None

        async for step in self._run_steps(steps):
            pass

        if step is not None:
            return step.chats[0]

        raise RuntimeError("Pipeline step failed.")

    async def run_many(self, n: int):
        """Run multiple completions in parallel.

        Parameters
        ----------
        n : int
            Number of parallel completions to run.

        Returns
        -------
        List[Chat]
            List of Chat objects containing the conversation messages.
        """
        return await asyncio.gather(*[self.run() for _ in range(n)])

    async def run_batch(self, inputs: list[dict]):
        """Run a batch of completions with different parameters.

        Parameters
        ----------
        params_list : list[dict]
            List of parameter dictionaries for each completion.

        Returns
        -------
        List[Any]
            List of completion results.
        """
        # TODO: Implement batch completions
        pass
