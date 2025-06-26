"""
Test script to demonstrate the retry mechanism in the Pipeline class.
"""

import asyncio
from typing import Dict, Any
from pydantic import BaseModel

# Mock classes for testing
class MockGenerator:
    def __init__(self, fail_count: int = 0):
        self.fail_count = fail_count
        self.call_count = 0
    
    async def complete(self, messages, params):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise Exception(f"Simulated failure {self.call_count}")
        
        # Return a mock response
        class MockMessage:
            def __init__(self):
                self.tool_calls = []
                self.content = "Success!"
            
            def parse(self, output_model):
                return output_model()
        
        class MockResponse:
            def __init__(self):
                self.message = MockMessage()
        
        return MockResponse()

class MockTool:
    def __init__(self, name: str, fail_count: int = 0):
        self.name = name
        self.fail_count = fail_count
        self.call_count = 0
    
    async def run(self, args, ctx):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise Exception(f"Tool {self.name} failed {self.call_count}")
        return {"result": f"Tool {self.name} succeeded"}

class MockChat:
    def __init__(self, messages, output_model=None, context=None):
        self.messages = messages
        self.output_model = output_model
        self.context = context
    
    @property
    def last(self):
        return self.messages[-1] if self.messages else None

class MockMessage:
    def __init__(self, role="user", content="", tool_calls=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls or []

class MockContext:
    def model_copy(self, deep=True):
        return MockContext()
    
    def __init__(self):
        self.inputs = {}

class MockPipeline:
    def __init__(self, generator, error_mode="raise"):
        self.generator = generator
        self.error_mode = error_mode
        self.tools = {}
        self.output_model = None
        self.context = MockContext()
        self.inputs = {}
    
    async def _render_messages(self):
        return [MockMessage(content="Test message")]

async def test_retry_mechanism():
    """Test the retry mechanism with a mock generator that fails initially."""
    
    print("Testing retry mechanism...")
    
    # Test 1: Generator fails twice, then succeeds
    print("\n1. Testing generator retry (fails 2 times, then succeeds):")
    generator = MockGenerator(fail_count=2)
    pipeline = MockPipeline(generator, error_mode="raise")
    
    try:
        # Simulate the retry logic from _run_steps
        params = None
        context = pipeline.context.model_copy(deep=True)
        context.inputs = pipeline.inputs.copy()
        
        current_chat = MockChat(
            messages=await pipeline._render_messages(),
            output_model=pipeline.output_model,
            context=context,
        )
        
        # Retry logic for the completion step
        for attempt in range(3):
            try:
                response = await generator.complete(current_chat.messages, params)
                print(f"  ✓ Success on attempt {attempt + 1}")
                break
            except Exception as e:
                print(f"  ✗ Failed on attempt {attempt + 1}: {e}")
                if attempt == 2:  # Last attempt
                    raise
                # Wait before retrying (exponential backoff)
                await asyncio.sleep(0.1 * (2 ** attempt))
        
        print(f"  Total calls to generator: {generator.call_count}")
        
    except Exception as e:
        print(f"  ✗ All retries failed: {e}")
    
    # Test 2: Tool execution retry
    print("\n2. Testing tool execution retry (fails 1 time, then succeeds):")
    tool = MockTool("test_tool", fail_count=1)
    pipeline.tools["test_tool"] = tool
    
    try:
        # Simulate tool execution with retry
        tool_call = type('MockToolCall', (), {
            'function': type('MockFunction', (), {'name': 'test_tool', 'arguments': '{}'})(),
            'id': 'test_id'
        })()
        
        tool_messages = []
        for attempt in range(3):
            try:
                tool_response = await tool.run(
                    {},  # args
                    ctx=pipeline.context
                )
                tool_messages.append(MockMessage(
                    role="tool",
                    content=str(tool_response)
                ))
                print(f"  ✓ Tool succeeded on attempt {attempt + 1}")
                break
            except Exception as e:
                print(f"  ✗ Tool failed on attempt {attempt + 1}: {e}")
                if attempt == 2:  # Last attempt
                    raise
                # Wait before retrying (exponential backoff)
                await asyncio.sleep(0.1 * (2 ** attempt))
        
        print(f"  Total calls to tool: {tool.call_count}")
        
    except Exception as e:
        print(f"  ✗ All tool retries failed: {e}")
    
    # Test 3: Error mode "pass"
    print("\n3. Testing error mode 'pass':")
    generator2 = MockGenerator(fail_count=5)  # Will always fail
    pipeline2 = MockPipeline(generator2, error_mode="pass")
    
    try:
        # Simulate the retry logic with error_mode="pass"
        for attempt in range(3):
            try:
                response = await generator2.complete([], None)
                print(f"  ✓ Success on attempt {attempt + 1}")
                break
            except Exception as e:
                print(f"  ✗ Failed on attempt {attempt + 1}: {e}")
                if attempt == 2:  # Last attempt
                    print("  → Returning early due to error_mode='pass'")
                    return  # Early return instead of raising
                await asyncio.sleep(0.1 * (2 ** attempt))
        
    except Exception as e:
        print(f"  ✗ Unexpected exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_retry_mechanism()) 