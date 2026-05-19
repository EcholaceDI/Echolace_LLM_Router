#!/usr/bin/env python3
"""
Provider Selection Example - Echolace LLM Router
Shows how to force specific providers and switch between them.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_router import LLMInterface

def main():
    print("🔧 Provider Selection Example")
    print("=" * 45)
    
    # Create interface
    llm = LLMInterface()
    
    # Show all available backends
    available = llm.available_backends()
    print(f"Available backends: {available}")
    
    if not available:
        print("❌ No real backends available. Install optional dependencies:")
        print("   pip install -e .[openai]  # For OpenAI")
        print("   pip install -e .[anthropic] # For Anthropic")
        print("   pip install -e .[all]      # For all backends")
        return
    
    # Test each available backend
    prompt = "What is 2 + 2?"
    
    for backend_name in available:
        print(f"\n🤖 Testing {backend_name}:")
        
        try:
            # Switch to this backend
            success = llm.switch(backend_name)
            if not success:
                print(f"   ❌ Failed to switch to {backend_name}")
                continue
            
            # Generate response
            response = llm.generate(prompt)
            print(f"   ✅ Response: {response}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Show current state
    print("\n📊 Final state:")
    info = llm.info()
    print(f"   Current backend: {info['backend']}")
    print(f"   Best backend: {info['best_backend']}")

if __name__ == "__main__":
    main()
