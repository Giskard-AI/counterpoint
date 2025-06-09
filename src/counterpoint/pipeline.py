from typing import Any, List, Type

from pydantic import BaseModel, Field

from counterpoint.chat import Chat, Message
from counterpoint.generator import Generator


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
    tools: List[Any] = Field(default_factory=list)
    generator: "Generator"
    output_model: Type[BaseModel] = None

    def with_tools(self, *tools):
        """Add tools to the pipeline.

        Parameters
        ----------
        *tools : Any
            Variable number of tools to add to the pipeline.

        Returns
        -------
        Pipeline
            The pipeline instance for method chaining.
        """
        self.tools = list(tools)
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

    async def run(self) -> Chat:
        """Run a single completion.

        Returns
        -------
        Chat
            A Chat object containing the conversation messages.
        """
        response = await self.generator.complete(self.messages, self.tools)

        return Chat(
            messages=self.messages + [response.message], output_model=self.output_model
        )

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
        return [await self.run() for _ in range(n)]

    async def run_batch(self, params_list: list[dict]):
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
