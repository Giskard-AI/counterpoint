import pytest
import asyncio
from typing import List
from pydantic import BaseModel

from counterpoint.workflow import AsyncWorkflowStep, NO_OUTPUT, NoOutput, async_gen_batch


class SimpleInput(BaseModel):
    value: int


class SimpleOutput(BaseModel):
    result: int


class FailingStep(AsyncWorkflowStep[SimpleInput, SimpleOutput]):
    async def run(self, input: SimpleInput) -> SimpleOutput:
        if input.value < 0:
            raise ValueError("Negative value not allowed")
        return SimpleOutput(result=input.value * 2)


class MultiplyStep(AsyncWorkflowStep[SimpleInput, SimpleOutput]):
    multiplier: int = 2

    async def run(self, input: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=input.value * self.multiplier)


class AddStep(AsyncWorkflowStep[SimpleOutput, SimpleOutput]):
    add_value: int = 10

    async def run(self, input: SimpleOutput) -> SimpleOutput:
        return SimpleOutput(result=input.result + self.add_value)


class ListProducerStep(AsyncWorkflowStep[SimpleInput, List[SimpleOutput]]):
    async def run(self, input: SimpleInput) -> List[SimpleOutput]:
        return [SimpleOutput(result=input.value + i) for i in range(3)]


class OutputFailingStep(AsyncWorkflowStep[SimpleOutput, SimpleOutput]):
    async def run(self, input: SimpleOutput) -> SimpleOutput:
        if input.result < 0:
            raise ValueError("Negative result not allowed")
        return SimpleOutput(result=input.result * 2)


class NegativeListProducerStep(AsyncWorkflowStep[SimpleInput, List[SimpleOutput]]):
    async def run(self, input: SimpleInput) -> List[SimpleOutput]:
        return [SimpleOutput(result=input.value - i) for i in range(3)]


# Test basic functionality
class TestBasicWorkflow:
    
    async def test_single_step_success(self):
        step = MultiplyStep(multiplier=3)
        input_data = SimpleInput(value=5)
        result = await step.run(input_data)
        assert result.result == 15

    async def test_single_step_error_raise_mode(self):
        step = FailingStep(error_mode="raise")
        input_data = SimpleInput(value=-5)
        
        with pytest.raises(ValueError, match="Negative value not allowed"):
            await step.run(input_data)

    async def test_run_one_error_pass_mode(self):
        step = FailingStep(error_mode="pass")
        input_data = SimpleInput(value=-5)
        result = await step._run_one(input_data)
        assert result is NO_OUTPUT


# Test streaming functionality
class TestStreamingWorkflow:
    
    async def test_run_stream_success(self):
        step = MultiplyStep(multiplier=2)
        inputs = [SimpleInput(value=i) for i in range(3)]
        
        results = []
        async for result in step.run_stream(async_gen_batch(inputs)):
            results.append(result)
        
        assert len(results) == 3
        assert results[0].result == 0
        assert results[1].result == 2
        assert results[2].result == 4

    async def test_run_stream_with_errors_pass_mode(self):
        step = FailingStep(error_mode="pass")
        inputs = [SimpleInput(value=i) for i in [-1, 1, -2, 2]]
        
        results = []
        async for result in step.run_stream(async_gen_batch(inputs)):
            results.append(result)
        
        # Only positive values should succeed
        assert len(results) == 2
        assert results[0].result == 2  # 1 * 2
        assert results[1].result == 4  # 2 * 2

    async def test_run_stream_with_errors_raise_mode(self):
        step = FailingStep(error_mode="raise")
        inputs = [SimpleInput(value=i) for i in [1, -1, 2]]
        
        with pytest.raises(ValueError, match="Negative value not allowed"):
            async for result in step.run_stream(async_gen_batch(inputs)):
                pass


# Test batch functionality
class TestBatchWorkflow:
    
    async def test_run_batch_success(self):
        step = MultiplyStep(multiplier=3)
        inputs = [SimpleInput(value=i) for i in range(4)]
        
        results = await step.run_batch(inputs)
        
        assert len(results) == 4
        assert results[0].result == 0
        assert results[1].result == 3
        assert results[2].result == 6
        assert results[3].result == 9

    async def test_run_batch_with_errors_pass_mode(self):
        step = FailingStep(error_mode="pass")
        inputs = [SimpleInput(value=i) for i in [-2, 1, -1, 3]]
        
        results = await step.run_batch(inputs)
        
        # Only positive values should succeed
        assert len(results) == 2
        assert results[0].result == 2  # 1 * 2
        assert results[1].result == 6  # 3 * 2

    async def test_run_batch_with_errors_raise_mode(self):
        step = FailingStep(error_mode="raise")
        inputs = [SimpleInput(value=i) for i in [1, -1, 2]]
        
        with pytest.raises(ValueError, match="Negative value not allowed"):
            await step.run_batch(inputs)

    async def test_run_many(self):
        step = MultiplyStep(multiplier=4)
        input_data = SimpleInput(value=5)
        
        results = await step.run_many(3, input_data)
        
        assert len(results) == 3
        assert all(result.result == 20 for result in results)

    async def test_stream_many(self):
        step = MultiplyStep(multiplier=2)
        input_data = SimpleInput(value=7)
        
        results = []
        async for result in step.stream_many(2, input_data):
            results.append(result)
        
        assert len(results) == 2
        assert all(result.result == 14 for result in results)

    async def test_stream_batch(self):
        step = MultiplyStep(multiplier=2)
        inputs = [SimpleInput(value=i) for i in range(3)]
        
        results = []
        async for result in step.stream_batch(inputs):
            results.append(result)
        
        assert len(results) == 3
        assert results[0].result == 0
        assert results[1].result == 2
        assert results[2].result == 4


# Test composition functionality
class TestWorkflowComposition:
    
    async def test_pipe_operator_success(self):
        step1 = MultiplyStep(multiplier=2)
        step2 = AddStep(add_value=10)
        composed = step1 | step2
        
        input_data = SimpleInput(value=5)
        result = await composed.run(input_data)
        
        assert result.result == 20  # (5 * 2) + 10

    async def test_pipe_operator_with_errors_raise_mode(self):
        step1 = FailingStep(error_mode="raise")
        step2 = AddStep(add_value=10)
        composed = step1 | step2
        
        input_data = SimpleInput(value=-5)
        
        with pytest.raises(ValueError, match="Negative value not allowed"):
            await composed.run(input_data)

    async def test_pipe_operator_with_errors_pass_mode(self):
        step1 = FailingStep(error_mode="pass")
        step2 = AddStep(add_value=10)
        composed = step1 | step2
        
        inputs = [SimpleInput(value=i) for i in [-1, 2, -3, 4]]
        results = await composed.run_batch(inputs)
        
        # Only positive values should make it through the pipeline
        assert len(results) == 2
        assert results[0].result == 14  # (2 * 2) + 10
        assert results[1].result == 18  # (4 * 2) + 10

    async def test_multiple_pipe_operators(self):
        step1 = MultiplyStep(multiplier=2)
        step2 = AddStep(add_value=5)
        step3 = AddStep(add_value=3)  # Use AddStep which takes SimpleOutput
        composed = step1 | step2 | step3
        
        input_data = SimpleInput(value=4)
        result = await composed.run(input_data)
        
        assert result.result == 16  # ((4 * 2) + 5) + 3

    async def test_composed_step_describe(self):
        step1 = MultiplyStep(multiplier=2, name="multiply")
        step2 = AddStep(add_value=10, name="add")
        composed = step1 | step2
        
        description = composed.describe()
        assert description == "multiply | add"


# Test map functionality
class TestWorkflowMap:
    
    async def test_map_success(self):
        step = MultiplyStep(multiplier=2)
        mapped = step.map(lambda x: SimpleOutput(result=x.result + 100))
        
        input_data = SimpleInput(value=5)
        result = await mapped.run(input_data)
        
        assert result.result == 110  # (5 * 2) + 100

    async def test_map_with_errors_pass_mode(self):
        step = FailingStep(error_mode="pass")
        mapped = step.map(lambda x: SimpleOutput(result=x.result + 100))
        
        inputs = [SimpleInput(value=i) for i in [-1, 2, -3]]
        results = await mapped.run_batch(inputs)
        
        assert len(results) == 1
        assert results[0].result == 104  # (2 * 2) + 100

    async def test_map_function_error_raise_mode(self):
        step = MultiplyStep(multiplier=2, error_mode="raise")
        
        def failing_map(x):
            if x.result > 5:
                raise ValueError("Result too large")
            return SimpleOutput(result=x.result + 100)
        
        mapped = step.map(failing_map)
        
        input_data = SimpleInput(value=5)  # Will produce result=10, which > 5
        
        with pytest.raises(ValueError, match="Result too large"):
            await mapped.run(input_data)

    async def test_map_function_error_pass_mode(self):
        step = MultiplyStep(multiplier=2, error_mode="pass")
        
        def failing_map(x):
            if x.result > 5:
                raise ValueError("Result too large")
            return SimpleOutput(result=x.result + 100)
        
        mapped = step.map(failing_map)
        
        inputs = [SimpleInput(value=i) for i in [1, 5, 2]]  # 5*2=10 will fail
        results = await mapped.run_batch(inputs)
        
        assert len(results) == 2
        assert results[0].result == 102  # (1 * 2) + 100
        assert results[1].result == 104  # (2 * 2) + 100

    async def test_mapped_step_describe(self):
        step = MultiplyStep(multiplier=2, name="multiply")
        mapped = step.map(lambda x: x)
        
        description = mapped.describe()
        assert description == "multiply |> map(<lambda>)"


# Test flat_map functionality
class TestWorkflowFlatMap:
    
    async def test_flat_map_success(self):
        list_step = ListProducerStep()
        add_step = AddStep(add_value=5)  # Use AddStep which takes SimpleOutput
        flat_mapped = list_step.flat_map(add_step)
        
        input_data = SimpleInput(value=10)
        results = await flat_mapped.run(input_data)
        
        assert len(results) == 3
        assert results[0].result == 15  # (10 + 0) + 5
        assert results[1].result == 16  # (10 + 1) + 5
        assert results[2].result == 17  # (10 + 2) + 5

    async def test_flat_map_type_error_raise_mode(self):
        # Using a step that doesn't return a list
        multiply_step = MultiplyStep(multiplier=2, error_mode="raise")
        add_step = AddStep(add_value=5)
        
        # This should fail because MultiplyStep returns SimpleOutput, not List[SimpleOutput]
        flat_mapped = multiply_step.flat_map(add_step)
        
        input_data = SimpleInput(value=5)
        
        with pytest.raises(TypeError, match="Expected list"):
            await flat_mapped.run(input_data)

    async def test_flat_map_with_errors_pass_mode(self):
        list_step = NegativeListProducerStep(error_mode="pass")
        failing_step = OutputFailingStep(error_mode="pass")  # Set error_mode to pass
        flat_mapped = list_step.flat_map(failing_step)
        
        # List step will produce [1, 0, -1], OutputFailingStep will fail on negative values
        input_data = SimpleInput(value=1)
        results = await flat_mapped.run(input_data)
        
        # Only positive values should succeed: [2, 0] (1*2, 0*2)
        assert len(results) == 2
        assert results[0].result == 2   # (1 - 0) * 2
        assert results[1].result == 0   # (1 - 1) * 2

    async def test_flat_mapped_step_describe(self):
        list_step = ListProducerStep(name="list_producer")
        multiply_step = MultiplyStep(multiplier=2, name="multiply")
        flat_mapped = list_step.flat_map(multiply_step)
        
        description = flat_mapped.describe()
        assert description == "list_producer ⨂ multiply"


# Test error mode inheritance
class TestErrorModeInheritance:
    
    async def test_composed_step_inherits_parent_error_mode(self):
        step1 = FailingStep(error_mode="pass")
        step2 = AddStep(add_value=10)
        composed = step1 | step2
        
        assert composed.error_mode == "pass"

    async def test_mapped_step_inherits_parent_error_mode(self):
        step = FailingStep(error_mode="pass")
        mapped = step.map(lambda x: x)
        
        assert mapped.error_mode == "pass"

    async def test_flat_mapped_step_inherits_parent_error_mode(self):
        step = ListProducerStep(error_mode="pass")
        multiply_step = MultiplyStep(multiplier=2)
        flat_mapped = step.flat_map(multiply_step)
        
        assert flat_mapped.error_mode == "pass"


# Test edge cases
class TestEdgeCases:
    
    async def test_empty_input_stream(self):
        step = MultiplyStep(multiplier=2)
        
        results = []
        async for result in step.run_stream(async_gen_batch([])):
            results.append(result)
        
        assert len(results) == 0

    async def test_empty_input_batch(self):
        step = MultiplyStep(multiplier=2)
        results = await step.run_batch([])
        
        assert len(results) == 0

    async def test_run_many_zero_count(self):
        step = MultiplyStep(multiplier=2)
        input_data = SimpleInput(value=5)
        
        results = await step.run_many(0, input_data)
        assert len(results) == 0

    async def test_no_output_is_singleton(self):
        step = FailingStep(error_mode="pass")
        input_data = SimpleInput(value=-5)
        
        result1 = await step._run_one(input_data)
        result2 = await step._run_one(input_data)
        
        assert result1 is NO_OUTPUT
        assert result2 is NO_OUTPUT
        assert result1 is result2

    async def test_no_output_model_properties(self):
        assert isinstance(NO_OUTPUT, NoOutput)
        assert isinstance(NO_OUTPUT, BaseModel)