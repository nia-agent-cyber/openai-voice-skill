#!/usr/bin/env python3
"""
Test script for function calling functionality.

Tests the function calling manager without needing actual voice calls.
"""

import asyncio
import json
import os
from datetime import datetime

from function_calling import function_manager

async def test_function_calling():
    """Test the function calling system."""
    print("🧪 Testing Function Calling System\n")
    
    # Test 1: List available functions
    print("1. Testing function definitions...")
    function_definitions = function_manager.get_openai_function_definitions()
    print(f"   📋 Available functions: {len(function_definitions)}")
    
    for func_def in function_definitions:
        print(f"   🔧 {func_def['name']}: {func_def['description']}")
    
    # Test 2: Test built-in time function
    print("\n2. Testing get_current_time function...")
    call_id = "test_call_functions_123"
    
    result = await function_manager.execute_function(
        call_id=call_id,
        function_name="get_current_time",
        arguments={"timezone": "UTC"}
    )
    
    if result.success:
        print(f"   ✅ Time function executed successfully")
        print(f"   ⏰ Result: {result.result['readable']}")
        print(f"   ⚡ Execution time: {result.execution_time:.3f}s")
    else:
        print(f"   ❌ Time function failed: {result.error}")
    
    # Test 3: Test function with invalid arguments
    print("\n3. Testing error handling...")
    result = await function_manager.execute_function(
        call_id=call_id,
        function_name="nonexistent_function",
        arguments={}
    )
    
    if not result.success:
        print(f"   ✅ Error handling working: {result.error}")
    else:
        print(f"   ❌ Error handling failed - should have rejected unknown function")
    
    # Test 4: Test function call history
    print("\n4. Testing function call history...")
    history = function_manager.get_call_function_history(call_id)
    print(f"   📋 Function calls in history: {len(history)}")
    
    for call in history:
        print(f"   📞 {call['timestamp']}: {call['function']} with args {call['arguments']}")
    
    # Test 5: Test OpenClaw function definitions (without actually calling)
    print("\n5. Testing OpenClaw function mapping...")
    openclaw_functions = [
        func for func in function_manager.functions.values() 
        if func.openclaw_tool
    ]
    
    print(f"   🔗 OpenClaw-integrated functions: {len(openclaw_functions)}")
    for func in openclaw_functions:
        print(f"   🛠️  {func.name} -> {func.openclaw_tool}")
    
    # Test 6: Test function registration
    print("\n6. Testing custom function registration...")
    
    def custom_math_function(a: float, b: float, operation: str = "add") -> dict:
        """Custom math function for testing."""
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Division by zero")
            result = a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return {"result": result, "operation": f"{a} {operation} {b} = {result}"}
    
    function_manager.register_function(
        name="math_calculator",
        description="Perform basic math operations",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
                "operation": {
                    "type": "string", 
                    "description": "Math operation to perform",
                    "enum": ["add", "subtract", "multiply", "divide"]
                }
            },
            "required": ["a", "b"]
        },
        handler=custom_math_function,
        examples=["What's 5 plus 3?", "Calculate 10 divided by 2"]
    )
    
    # Test the custom function
    result = await function_manager.execute_function(
        call_id=call_id,
        function_name="math_calculator",
        arguments={"a": 15, "b": 3, "operation": "multiply"}
    )
    
    if result.success:
        print(f"   ✅ Custom function executed successfully")
        print(f"   🧮 Result: {result.result['operation']}")
    else:
        print(f"   ❌ Custom function failed: {result.error}")
    
    # Test 7: Verify updated function count
    print("\n7. Testing updated function definitions...")
    updated_definitions = function_manager.get_openai_function_definitions()
    print(f"   📋 Functions after registration: {len(updated_definitions)}")
    
    # Check if our custom function is included
    math_func = next((f for f in updated_definitions if f['name'] == 'math_calculator'), None)
    if math_func:
        print(f"   ✅ Custom function found in definitions")
        print(f"   📝 Parameters: {math_func['parameters']['required']}")
    else:
        print(f"   ❌ Custom function not found in definitions")
    
    print("\n🎯 Function calling system test complete!")
    
    # Cleanup
    print("\nCleanup:")
    function_manager.clear_call_history(call_id)
    cleaned_history = function_manager.get_call_function_history(call_id)
    print(f"   ✅ Call history cleared: {len(cleaned_history)} calls remaining")

if __name__ == "__main__":
    asyncio.run(test_function_calling())