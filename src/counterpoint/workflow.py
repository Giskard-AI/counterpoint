import asyncio
from typing import (
    AsyncIterable,
    AsyncGenerator,
    Callable,
    TypeVar,
    Generic,
    List,
    Union,
    Literal,
)
from pydantic import BaseModel

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")
NewOutput = TypeVar("NewOutput")

ErrorMode = Literal["raise", "pass"]

class NoOutputError(Exception):
    """Raised when a workflow step produces no output due to error in 'pass' mode."""
    pass

async def async_gen_batch(inputs: list[InputType]) -> AsyncGenerator[InputType, None]:
    for item in inputs:
        yield item

async def async_gen_many(n: int, input: InputType) -> AsyncGenerator[InputType, None]:
    for _ in range(n):
        yield input

class AsyncWorkflowStep(BaseModel, Generic[InputType, OutputType]):
    name: str = ""
    error_mode: ErrorMode = "raise"

    async def run(self, input: InputType) -> OutputType:
        raise NotImplementedError()

    async def run_stream(
        self, inputs: AsyncIterable[InputType]
    ) -> AsyncGenerator[OutputType, None]:
        tasks = []

        async def run_one(item: InputType):
            try:
                return await self.run(item)
            except NoOutputError:
                return None  # Indicates no output should be yielded
            except Exception as e:
                if self.error_mode == "raise":
                    raise
                return e  # We return Exception, so caller can handle it

        async for item in inputs:
            tasks.append(run_one(item))  # no need to wrap in task yet

        for coro in asyncio.as_completed([asyncio.create_task(t) for t in tasks]):
            result = await coro
            if result is None:
                continue  # Skip NoOutputError cases - no output to yield
            if isinstance(result, Exception):
                if self.error_mode == "raise":
                    raise result
                continue  # skip or yield exception depending on what you want
            yield result

    async def run_batch(self, inputs: list[InputType]) -> list[OutputType]:
        return await asyncio.gather(
            *(self.run(inp) for inp in inputs),
            return_exceptions=self.error_mode != "raise"
        )
        
    async def stream_batch(self, inputs: list[InputType]) -> AsyncGenerator[OutputType, None]:
        async for item in self.run_stream(async_gen_batch(inputs)):
            if isinstance(item, Exception):
                if self.error_mode == "raise":
                    raise item
                continue
            yield item

    async def stream_many(self, n: int, input: InputType) -> AsyncGenerator[OutputType, None]:
        async for result in self.run_stream(async_gen_many(n, input)):
            yield result
    
    async def run_many(self, n: int, input: InputType) -> list[OutputType]:
        return [output async for output in self.run_stream(async_gen_many(n, input))]

    def __or__(
        self, next_step: "AsyncWorkflowStep[OutputType, NewOutput]"
    ) -> "AsyncWorkflowStep[InputType, NewOutput]":
        parent = self

        class ComposedStep(AsyncWorkflowStep[InputType, NewOutput]):
            error_mode: ErrorMode = parent.error_mode

            async def run(self, input: InputType) -> NewOutput:
                try:
                    intermediate = await parent.run(input)
                    return await next_step.run(intermediate)
                except Exception:
                    if self.error_mode == "raise":
                        raise
                    raise NoOutputError("Step produced no output due to error in 'pass' mode")

            async def run_stream(
                self, inputs: AsyncIterable[InputType]
            ) -> AsyncGenerator[Union[NewOutput, Exception], None]:
                async for item in parent.run_stream(inputs):
                    if item is not None:
                        try:
                            result = await next_step.run(item)
                            yield result
                        except NoOutputError:
                            continue  # Skip items that produce no output
                        except Exception:
                            if self.error_mode == "raise":
                                raise

            def describe(self) -> str:
                return f"{parent.describe()} | {next_step.describe()}"

        return ComposedStep()

    def map(
        self, fn: Callable[[OutputType], NewOutput]
    ) -> "AsyncWorkflowStep[InputType, NewOutput]":
        parent = self

        class MappedStep(AsyncWorkflowStep[InputType, NewOutput]):
            error_mode: ErrorMode = parent.error_mode

            async def run(self, input: InputType) -> NewOutput:
                try:
                    result = await parent.run(input)
                    return fn(result)
                except Exception:
                    if self.error_mode == "raise":
                        raise
                    raise NoOutputError("Step produced no output due to error in 'pass' mode")

            async def run_stream(
                self, inputs: AsyncIterable[InputType]
            ) -> AsyncGenerator[Union[NewOutput, Exception], None]:
                async for result in parent.run_stream(inputs):
                    if result is not None:
                        try:
                            yield fn(result)
                        except Exception:
                            if self.error_mode == "raise":
                                raise
                            # In 'pass' mode, simply don't yield anything for failed items

            def describe(self) -> str:
                return f"{parent.describe()} |> map({fn.__name__})"

        return MappedStep()

    def flat_map(
        self, next_step: "AsyncWorkflowStep[OutputType, NewOutput]"
    ) -> "AsyncWorkflowStep[InputType, List[NewOutput]]":
        parent = self

        class FlatMappedStep(AsyncWorkflowStep[InputType, List[NewOutput]]):
            error_mode: ErrorMode = parent.error_mode

            async def run(self, input: InputType) -> List[NewOutput]:
                try:
                    outputs = await parent.run(input)
                    if not isinstance(outputs, list):
                        raise TypeError(f"Expected list, got {type(outputs)}")
                    return await asyncio.gather(*(next_step.run(x) for x in outputs))
                except Exception:
                    if self.error_mode == "raise":
                        raise
                    return []

            async def run_stream(
                self, inputs: AsyncIterable[InputType]
            ) -> AsyncGenerator[Union[List[NewOutput], Exception], None]:
                async for input_item in inputs:
                    try:
                        results = await self.run(input_item)
                        if results:
                            yield results
                    except Exception as e:
                        if self.error_mode == "raise":
                            raise e

            def describe(self) -> str:
                return f"{parent.describe()} ⨂ {next_step.describe()}"

        return FlatMappedStep()

    def describe(self) -> str:
        return self.name or self.__class__.__name__
