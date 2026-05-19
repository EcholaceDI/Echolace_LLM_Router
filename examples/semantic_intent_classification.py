#!/usr/bin/env python3
"""
Semantic intent classification demo (Echolace LLM Router).

This script demonstrates:
- Intent prediction via llm.intent()
- The returned top-k intent candidates (and optional route info)

Run from project root:
  python examples/semantic_intent_classification.py
"""

from __future__ import annotations

import json

from llm_router import LLMInterface


def main() -> None:
    llm = LLMInterface(intent_routing=True)

    prompts = [
        "Write a Python function to parse a CSV file and return a list of dicts.",
        "Help me debug why my unit tests are flaky in CI but not locally.",
        "Translate this sentence to Spanish: 'The router chooses the best backend.'",
        "Give me a creative opening line for a sci-fi story about a silent AI.",
    ]

    for p in prompts:
        print("\n== Prompt ==")
        print(p)
        print("\n== Intent candidates ==")
        result = llm.intent(p, top_k=3, include_route=True)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
