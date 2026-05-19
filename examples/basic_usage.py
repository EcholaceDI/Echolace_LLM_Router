#!/usr/bin/env python3
"""
Basic Usage Example - Echolace LLM Router
Demonstrates simple text generation with auto-backend selection.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_router import LLMInterface

def main():
    print("🚀 Basic Usage Example")
    print("=" * 40)
    
    # Create interface - auto-selects best available backend
    llm = LLMInterface()
    
    # Show current setup
    info = llm.info()
    print(f"Using backend: {info['backend']}")
    print(f"Available backends: {info['available_backends']}")
    
    # Generate text
    print("\n📝 Generating text:")
    prompt = "Write a haiku about programming"
    response = llm.generate(prompt)
    print(f"Prompt: {prompt}")
    print(f"Response: {response}")
    
    # Test streaming
    print("\n🌊 Streaming example:")
    prompt = "Count to 5"
    print(f"Prompt: {prompt}")
    print("Response: ", end="")
    
    for chunk in llm.stream(prompt):
        token = chunk.get("token", "")
        print(token, end="", flush=True)
    print()  # Newline

if __name__ == "__main__":
    main()
