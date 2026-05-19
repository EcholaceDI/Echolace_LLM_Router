#!/usr/bin/env python3
"""
Basic usage demo (Echolace LLM Router).

Demonstrates:
- auto backend selection
- generate()
- stream()

Run from project root:
  python examples/basic_usage.py
"""

from __future__ import annotations

from llm_router import LLMInterface


def main() -> None:
    llm = LLMInterface()

    info = llm.info()
    print("== Router info ==")
    print(f"Backend: {info['backend']}")
    print(f"Available: {info['available_backends']}")

    prompt = "Write a haiku about programming."
    print("\n== generate() ==")
    print(f"Prompt: {prompt}")
    print("Response:")
    print(llm.generate(prompt))

    prompt = "Count to 5, one number per line."
    print("\n== stream() ==")
    print(f"Prompt: {prompt}")
    print("Response:")
    for chunk in llm.stream(prompt):
        token = chunk.get("token", "")
        print(token, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
