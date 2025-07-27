import json
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generic,
    List,
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
from counterpoint.workflow import AsyncWorkflowStep, async_gen_many

class TemplateReference(BaseModel):
    """A reference to a template file that will be loaded at runtime."""
    template_name: str

class PipelineStep(BaseModel):
    """A step in a pipeline."""
    pipeline: "Pipeline"
    chats: List[Chat]
    previous: Optional["PipelineStep"] = Field(default=None)

StepGenerator = AsyncGenerator[PipelineStep, None]

OutputType = TypeVar("OutputType", bound=BaseModel)

class ChatWorkflow(AsyncWorkflowStep[dict | None, OutputType], Generic[OutputType]):
    """
    A pipeline for handling chat completions, compatible with AsyncWorkflowStep.

    Parameters
    ----------
    generator : BaseGenerator
        The generator instance to use for completions.
    messages : List[Message | MessageTemplate | TemplateReference], optional
        List of chat messages, templates, or template references.
    tools : Dict[str, Tool], optional
        Dictionary of tools available to the pipeline.
    output_model : Type[OutputType], optional
        The output model to use for the pipeline.
    prompt_manager : PromptsManager, optional
        The prompt manager to use for rendering templates.
    context : RunContext, optional
        The context for the pipeline.
    error_mode : OnErrorAction, optional
        Error handling behavior ("raise" or "pass").
    """

    generator: "BaseGenerator"
    messages: List[Message | MessageTemplate | TemplateReference] = Field(default_factory=list)
    tools: Dict[str, Tool] = Field(default_factory=dict)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    output_model: Type[OutputType] | None = Field(default=None)
    prompt_manager: PromptsManager = Field(default_factory=get_prompts_manager)
    context: RunContext = Field(default_factory=RunContext)
    max_steps: int | None = Field(default=None)

    def chat(self, message: str | Message, role: Role = "user") -> "Pipeline":
        """
        Add a chat message to the pipeline.

        Parameters
        ----------
        message : str | Message
            The message content or Message object.
        role : Role, optional
            The role of the message (default is "user").

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        if isinstance(message, str):
            message = MessageTemplate(role=role, content_template=message)
        self.messages.append(message)
        return self

    def template(self, template_name: str) -> "Pipeline":
        """
        Load messages from a template file.

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

    def with_tools(self, *tools: Tool) -> "Pipeline":
        """
        Add tools to the pipeline.

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
        """
        Set the output model for the pipeline.

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
        """
        Set the context for the pipeline.

        Parameters
        ----------
        context : RunContext
            The context to use for the pipeline.

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        self.context = context
        return self
    
    def with_max_steps(self, max_steps: int) -> "Pipeline":
        """
        Set the maximum number of steps for the pipeline.
        """
        self.max_steps = max_steps
        return self
    
    async def _run_steps(self, inputs: dict | None = None) -> StepGenerator:
        params = GenerationParams(
            tools=list(self.tools.values()),
            response_format=self.output_model,
        )

        context = self.context.model_copy(deep=True)
        context.inputs = self.inputs | (inputs or dict())

        current_step = None
        current_step_num = 0
        current_chat = Chat(
            messages=await self._render_messages(),
            output_model=self.output_model,
            context=context,
        )
        while True:
            if self.max_steps is not None and current_step_num >= self.max_steps:
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

    async def run(self, inputs: dict | None = None) -> OutputType:
        """
        Run the pipeline with the given input.

        Parameters
        ----------
        input : dict
            The input variables for the pipeline.

        Returns
        -------
        OutputType
            The output of the pipeline, as defined by the output_model.
        """
        step = None

        async for step in self._run_steps(inputs):
            pass

        if step is not None:
            return step.chats[0]

        raise RuntimeError("Pipeline step failed.")
    
    async def stream_many(self, n: int, input: dict | None = None) -> AsyncGenerator[OutputType, None]:
        async for result in super().run_stream(async_gen_many(n, input)):
            yield result
    
    async def run_many(self, n: int, input: dict | None = None) -> List[OutputType]:
        return await super().run_many(n, input)
    

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
    """
    Generate output instructions for the model based on the output schema.

    Parameters
    ----------
    output_model : Type[BaseModel]
        The output model class.

    Returns
    -------
    str
        Instructions for formatting the output as JSON.
    """
    return f"Provide your answer in JSON format, respecting this schema:\n{output_model.model_json_schema()}"
