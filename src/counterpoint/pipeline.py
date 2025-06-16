import asyncio
import json
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Type,
    TypeVar,
)

from pydantic import BaseModel, Field

from counterpoint.chat import Chat, Message, Role
from counterpoint.context import RunContext
from counterpoint.generators import BaseGenerator, GenerationParams
from counterpoint.templates import MessageTemplate, PromptsManager, get_prompts_manager
from counterpoint.tools.tool import Tool


class TemplateReference(BaseModel):
    """A reference to a template file that will be loaded at runtime."""

    template_name: str


class PipelineStep(BaseModel):
    """A step in a pipeline."""

    pipeline: "Pipeline"
    chats: List[Chat]
    previous: Optional["PipelineStep"] = Field(default=None)


StepGenerator = AsyncGenerator[PipelineStep, None]
OnErrorAction = Literal["raise", "pass"]


OutputType = TypeVar("OutputType", bound=BaseModel)


class Pipeline(BaseModel, Generic[OutputType]):
    """A pipeline for handling chat completions.

    Attributes
    ----------
    messages : List[Message]
        List of chat messages in the conversation.
    model : str
        The model identifier to use for completions.
    tools : List[Any]
        List of tools available to the pipeline.
    generator : BaseGenerator
        The generator instance to use for completions.
    prompt_manager : PromptsManager
        The prompt manager to use for rendering templates.
    """

    generator: "BaseGenerator"

    messages: List[Message | MessageTemplate | TemplateReference] = Field(
        default_factory=list
    )
    tools: Dict[str, Tool] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    output_model: Type[OutputType] | None = Field(default=None)
    prompt_manager: PromptsManager = Field(default_factory=get_prompts_manager)
    context: RunContext = Field(default_factory=RunContext)
    error_mode: OnErrorAction = Field(default="raise")

    def chat(self, message: str | Message, role: Role = "user") -> "Pipeline":
        """Add a chat message to the pipeline."""
        if isinstance(message, str):
            message = MessageTemplate(role=role, content_template=message)
        self.messages.append(message)
        return self

    def template(self, template_name: str) -> "Pipeline":
        """Load messages from a template file.

        Parameters
        ----------
        template_name : str
            The template name in dot notation (e.g., "crescendo.master_prompt")

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        template_message = TemplateReference(template_name=template_name)
        self.messages.append(template_message)
        return self

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

    def with_output(self, output_model: Type[OutputType]) -> "Pipeline[OutputType]":
        """Set the output model for the pipeline.

        Parameters
        ----------
        output_model : Type[OutputType]
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

    def with_context(self, context: RunContext) -> "Pipeline":
        """Set the context for the pipeline."""
        self.context = context
        return self

    def on_error(self, error_mode: OnErrorAction) -> "Pipeline":
        """Set the error handling behavior for the pipeline."""
        self.error_mode = error_mode
        return self

    async def _run_steps(self, max_steps: int | None = None) -> StepGenerator:
        params = GenerationParams(
            tools=list(self.tools.values()),
            response_format=self.output_model,
        )

        context = self.context.model_copy()
        context.inputs = self.inputs.copy()

        current_step = None
        current_step_num = 0
        current_chat = Chat(
            messages=await self._render_messages(),
            output_model=self.output_model,
            context=context,
        )
        while True:
            if max_steps is not None and current_step_num >= max_steps:
                break

            response = await self.generator.complete(current_chat.messages, params)

            current_step_num += 1
            current_chat = Chat(
                messages=current_chat.messages + [response.message],
                output_model=self.output_model,
                context=current_chat.context,
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
                    tool_response = await tool.run(
                        json.loads(tool_call.function.arguments),
                        ctx=current_step.chats[0].context,
                    )
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
                    context=current_chat.context,
                )
            else:
                # All done, no tool calls, we stop here.
                return

    async def run(self, max_steps: int | None = None) -> Chat[OutputType]:
        """Runs the pipeline.

        Parameters
        ----------
        max_steps : int, optional
            The number of steps to run. If not provided, the pipeline will run until the chat is complete.

        Returns
        -------
        Chat[OutputType]
            A Chat object containing the conversation messages.
        """
        step = None

        async for step in self._run_steps(max_steps):
            pass

        if step is not None:
            return step.chats[0]

        raise RuntimeError("Pipeline step failed.")

    async def run_many(self, n: int, max_steps: int | None = None):
        """Run multiple completions in parallel.

        Parameters
        ----------
        n : int
            Number of parallel completions to run.
        max_steps : int, optional
            The maximum number of steps to run for each completion.

        Returns
        -------
        List[Chat]
            List of Chat objects containing the conversation messages.
        """
        return await asyncio.gather(
            *[self.run(max_steps=max_steps) for _ in range(n)],
            return_exceptions=self.error_mode != "raise",
        )

    async def run_batch(self, inputs: list[dict], max_steps: int | None = None):
        """Run a batch of completions with different parameters.

        Parameters
        ----------
        params_list : list[dict]
            List of parameter dictionaries for each completion.
        max_steps : int, optional
            The maximum number of steps to run for each completion.

        Returns
        -------
        List[Any]
            List of completion results.
        """
        pipelines = [self.model_copy().with_inputs(**params) for params in inputs]

        return await asyncio.gather(
            *[pipeline.run(max_steps=max_steps) for pipeline in pipelines],
            return_exceptions=self.error_mode != "raise",
        )

    async def _render_messages(self) -> List[Message]:
        rendered_messages = []
        context_vars = {}
        if self.output_model is not None:
            context_vars["_instr_output"] = _output_instructions(self.output_model)
        context_vars.update(self.inputs)
        for message in self.messages:
            if isinstance(message, MessageTemplate):
                rendered_messages.append(message.render(**context_vars))
            elif isinstance(message, TemplateReference):
                template_messages = await self.prompt_manager.render_template(
                    message.template_name, context_vars
                )
                rendered_messages.extend(template_messages)
            else:
                rendered_messages.append(message)
        return rendered_messages


def _output_instructions(output_model: Type[BaseModel]) -> str:
    return f"Provide your answer in JSON format, respecting this schema:\n{output_model.model_json_schema()}"
