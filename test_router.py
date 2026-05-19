#!/usr/bin/env python3
"""
Echolace LLM Router - Simple Test Script
Run this script to verify the router is working correctly.
"""

def main():
    """Test the LLM Router functionality."""
    try:
        from llm_router import LLMInterface
        
        print("🚀 Echolace LLM Router Test")
        print("=" * 50)
        
        # Create interface
        llm = LLMInterface()
        
        # Show info
        info = llm.info()
        print(f"Current Backend: {info['backend']}")
        print(f"Available Backends: {info['available_backends']}")
        print(f"Best Backend: {info['best_backend']}")
        
        # Test generation
        print("\n📝 Testing Generation:")
        result = llm.generate("Hello, world!")
        print(f"Result: {result}")
        
        # Test diagnostics
        print("\n🔍 Running Diagnostics:")
        diagnostics = llm.diagnostics()
        print(f"System: {diagnostics.get('system', 'Unknown')}")
        print(f"Python: {diagnostics.get('python_version', 'Unknown')}")
        
        print("\n✅ Router is working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
