#!/usr/bin/env python3
"""
Provider selection demo (Echolace LLM Router).

Shows how to:
- list available backends
- switch between them programmatically

Run from project root:
  python examples/provider_selection.py
"""

from __future__ import annotations

from llm_router import LLMInterface


def main() -> None:
    print("Provider Selection Example")
    print("=" * 45)

    llm = LLMInterface()
    available = llm.available_backends()
    print(f"Available backends: {available}")

    if not available:
        print("No real backends available. Install optional dependencies, e.g.:")
        print("  pip install -e .[openai]      # OpenAI")
        print("  pip install -e .[anthropic]   # Anthropic")
        print("  pip install -e .[google]      # Gemini")
        print("  pip install -e .[all]         # Everything")
        return

    prompt = "What is 2 + 2?"
    for backend_name in available:
        print(f"\nTesting {backend_name}:")
        try:
            if not llm.switch(backend_name):
                print(f"  Failed to switch to {backend_name}")
                continue
            response = llm.generate(prompt)
            print(f"  Response: {response}")
        except Exception as exc:
            print(f"  Error: {exc}")

    info = llm.info()
    print("\nFinal state:")
    print(f"  Current backend: {info['backend']}")
    print(f"  Best backend: {info['best_backend']}")


if __name__ == "__main__":
    main()

