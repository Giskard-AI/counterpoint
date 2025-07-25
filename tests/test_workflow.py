import pytest
import asyncio
from pydantic import BaseModel
from src.counterpoint.workflow import AsyncWorkflowStep

class InputModel(BaseModel):
    value: int

class OutputModel(BaseModel):
    value: int

class DoubleStep(AsyncWorkflowStep[InputModel, OutputModel]):
    name: str = "double"
    async def run(self, input: InputModel) -> OutputModel:
        return OutputModel(value=input.value * 2)
    def describe(self) -> str:
        return f"{self.name}: DoubleStep"

class ToListStep(AsyncWorkflowStep[InputModel, list[OutputModel]]):
    name: str = "tolist"
    async def run(self, input: InputModel) -> list[OutputModel]:
        return [OutputModel(value=input.value), OutputModel(value=input.value + 1)]
    def describe(self) -> str:
        return f"{self.name}: ToListStep"

class AddOneStep(AsyncWorkflowStep[OutputModel, OutputModel]):
    name: str = "addone"
    async def run(self, input: OutputModel) -> OutputModel:
        return OutputModel(value=input.value + 1)
    def describe(self) -> str:
        return f"{self.name}: AddOneStep"

class DummyStep(AsyncWorkflowStep[InputModel, OutputModel]):
    name: str = "dummy"
    pass

def test_step_run_notimplemented():
    """Test that AsyncWorkflowStep.run raises NotImplementedError by default.
    """
    step = DummyStep()
    with pytest.raises(NotImplementedError):
        asyncio.run(step.run(InputModel(value=1)))

async def test_step_map():
    """Test map method applies a function to the async result.
    """
    step = DoubleStep()
    mapped = step.map(lambda out: OutputModel(value=out.value + 10))
    result = await mapped.run(InputModel(value=2))
    assert result.value == 14

async def test_step_flatmap():
    """Test flat_map applies next_step to each item in a list result.
    """
    step = ToListStep()
    next_step = AddOneStep()
    flatmapped = step.flat_map(next_step)
    results = await flatmapped.run(InputModel(value=3))
    assert [r.value for r in results] == [4, 5]

async def test_step_flatmap_typeerror():
    """Test flat_map raises TypeError if parent result is not a list.
    """
    class NotAListStep(AsyncWorkflowStep[InputModel, OutputModel]):
        name: str = "notalist"
        async def run(self, input: InputModel) -> OutputModel:
            return OutputModel(value=input.value)
        def describe(self) -> str:
            return f"{self.name}: NotAListStep"
    step = NotAListStep()
    next_step = AddOneStep()
    flatmapped = step.flat_map(next_step)
    with pytest.raises(TypeError):
        await flatmapped.run(InputModel(value=1))

async def test_step_or_operator():
    """Test __or__ operator chains steps and runs in order.
    """
    step1 = DoubleStep()
    step2 = AddOneStep()
    composed = step1 | step2
    result = await composed.run(InputModel(value=5))
    assert result.value == 11

async def test_describe_methods():
    """Test describe methods for all step types, including map and flat_map.
    """
    step = DoubleStep()
    mapped = step.map(lambda out: OutputModel(value=out.value + 1))
    tolist = ToListStep()
    addone = AddOneStep()
    flatmapped = tolist.flat_map(addone)
    composed = step | addone
    assert "double" in step.describe()
    assert "DoubleStep" in step.describe()
    assert "double: DoubleStep |> map(<lambda>)" in mapped.describe()
    assert "tolist" in tolist.describe()
    assert "addone" in addone.describe()
    assert "⨂" in flatmapped.describe()
    assert "double" in composed.describe() and "addone" in composed.describe() 

async def test_chain_multiple_steps():
    """Test chaining more than two steps using | operator."""
    step1 = DoubleStep()
    step2 = AddOneStep()
    step3 = AddOneStep()
    composed = step1 | step2 | step3
    result = await composed.run(InputModel(value=2))
    # ((2 * 2) + 1) + 1 = 6
    assert result.value == 6

async def test_chain_with_map():
    """Test chaining a mapped step with | operator."""
    step = DoubleStep()
    mapped = step.map(lambda out: OutputModel(value=out.value + 5))
    addone = AddOneStep()
    composed = mapped | addone
    result = await composed.run(InputModel(value=3))
    # (3 * 2) + 5 = 11, then +1 = 12
    assert result.value == 12

async def test_chain_with_flatmap():
    """Test chaining a flat_mapped step with | operator."""
    tolist = ToListStep()
    addone = AddOneStep()
    flatmapped = tolist.flat_map(addone)
    # flatmapped returns a list, so chain another step that expects a list
    class SumStep(AsyncWorkflowStep[list[OutputModel], OutputModel]):
        name: str = "sum"
        async def run(self, input: list[OutputModel]) -> OutputModel:
            return OutputModel(value=sum(x.value for x in input))
        def describe(self) -> str:
            return f"{self.name}: SumStep"
    sumstep = SumStep()
    composed = flatmapped | sumstep
    result = await composed.run(InputModel(value=4))
    # ToListStep: [4,5], AddOneStep: [5,6], SumStep: 11
    assert result.value == 11

async def test_chain_mixed_composed_and_step():
    """Test chaining a composed workflow with a single step."""
    step1 = DoubleStep()
    step2 = AddOneStep()
    composed = step1 | step2
    # Now chain another AddOneStep
    final = composed | AddOneStep()
    result = await final.run(InputModel(value=2))
    # ((2*2)+1)+1 = 6
    assert result.value == 6 

@pytest.mark.asyncio
async def test_run_stream_single_step():
    """Test run_stream for a single step."""
    step = DoubleStep()
    inputs = [InputModel(value=i) for i in range(3)]
    async def input_gen():
        for x in inputs:
            yield x
    results = [r async for r in step.run_stream(input_gen())]
    assert [r.value for r in results] == [0, 2, 4]

@pytest.mark.asyncio
async def test_run_stream_mapped_step():
    """Test run_stream for a mapped step."""
    step = DoubleStep().map(lambda out: OutputModel(value=out.value + 5))
    inputs = [InputModel(value=i) for i in range(2)]
    async def input_gen():
        for x in inputs:
            yield x
    results = [r async for r in step.run_stream(input_gen())]
    assert [r.value for r in results] == [5, 7]

@pytest.mark.asyncio
async def test_run_stream_flatmapped_step():
    """Test run_stream for a flat_mapped step."""
    step = ToListStep().flat_map(AddOneStep())
    inputs = [InputModel(value=1), InputModel(value=2)]
    async def input_gen():
        for x in inputs:
            yield x
    results = [r async for r in step.run_stream(input_gen())]
    # ToListStep: [1,2] -> AddOneStep: [2,3], [2,3] -> [3,4]
    assert results == [[OutputModel(value=2), OutputModel(value=3)], [OutputModel(value=3), OutputModel(value=4)]]
    assert [[x.value for x in group] for group in results] == [[2, 3], [3, 4]]

@pytest.mark.asyncio
async def test_run_stream_composed_step():
    """Test run_stream for a composed step using | operator."""
    step = DoubleStep() | AddOneStep()
    inputs = [InputModel(value=2), InputModel(value=3)]
    async def input_gen():
        for x in inputs:
            yield x
    results = [r async for r in step.run_stream(input_gen())]
    # (2*2)+1=5, (3*2)+1=7
    assert [r.value for r in results] == [5, 7] 