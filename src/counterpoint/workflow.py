import asyncio
from typing import (
    AsyncIterable,
    AsyncGenerator,
    Callable,
    TypeVar,
    Generic,
    List,
    Literal,
)
from pydantic import BaseModel

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")
NewOutput = TypeVar("NewOutput")

ErrorMode = Literal["raise", "pass"]

# We use this to indicate that a workflow step produced no output due to error in 'pass' mode.
class NoOutput(BaseModel):
    pass

NO_OUTPUT = NoOutput()

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
    
    async def _run_one(self, input: InputType) -> OutputType:
        try:
            return await self.run(input)
        except Exception:
            if self.error_mode == "raise":
                raise
            return NO_OUTPUT

    async def run_stream(
        self, inputs: AsyncIterable[InputType]
    ) -> AsyncGenerator[OutputType, None]:
        tasks = []

        async for item in inputs:
            tasks.append(self._run_one(item))

        for coro in asyncio.as_completed([asyncio.create_task(t) for t in tasks]):
            result = await coro
            if result is NO_OUTPUT:
                continue
            if isinstance(result, Exception):
                raise result
            yield result

    async def run_batch(self, inputs: list[InputType]) -> list[OutputType]:
        results = await asyncio.gather(
            *(self._run_one(inp) for inp in inputs),
        )
        return [result for result in results if result is not NO_OUTPUT]
        
    async def stream_batch(self, inputs: list[InputType]) -> AsyncGenerator[OutputType, None]:
        async for item in self.run_stream(async_gen_batch(inputs)):
            if item is NO_OUTPUT:
                continue
            if isinstance(item, Exception):
                raise item
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
                intermediate = await parent.run(input)
                return await next_step.run(intermediate)
           
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
                result = await parent.run(input)
                return fn(result)

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
                outputs = await parent.run(input)
                if not isinstance(outputs, list):
                    raise TypeError(f"Expected list, got {type(outputs)}")
                
                # Use _run_one to respect error_mode
                results = await asyncio.gather(*(next_step._run_one(x) for x in outputs))
                return [result for result in results if result is not NO_OUTPUT]

            def describe(self) -> str:
                return f"{parent.describe()} ⨂ {next_step.describe()}"

        return FlatMappedStep()

    def describe(self) -> str:
        return self.name or self.__class__.__name__