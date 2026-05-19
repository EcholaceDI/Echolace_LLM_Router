#!/usr/bin/env python3
"""
Privacy-first routing demo (Echolace LLM Router).

This script demonstrates:
- Structured privacy scanning
- How to request a privacy-first routing plan
- How to generate a response with privacy-first mode enabled

Run from project root:
  python examples/privacy_first_routing.py
"""

from __future__ import annotations

import json

from llm_router import LLMInterface


def main() -> None:
    llm = LLMInterface(
        privacy_first=True,
        # Prefer a local backend for privacy checks, but fall back to cloud if needed.
        local_privacy_backend="ollama",
        fallback_cloud_provider="openai_standard",
        fallback_cloud_model="gpt-4o-mini",
        privacy_profile="default",
    )

    payload = {
        "user_id": "u_12345",
        "message": "Please summarize the following: My SSN is 123-45-6789 and my phone is (555) 010-0000.",
        "notes": ["internal-only", "do-not-log"],
    }

    print("== Privacy scan (structured payload) ==")
    scan = llm.scan(payload)
    print(json.dumps(scan, indent=2, sort_keys=True))

    print("\n== Routing plan (privacy-first) ==")
    plan = llm.routing_plan(payload)
    print(json.dumps(plan, indent=2, sort_keys=True))

    print("\n== Generate (privacy-first) ==")
    prompt = "Summarize the user's message in one sentence and do not repeat sensitive identifiers."
    try:
        out = llm.generate(prompt, context=payload)
    except TypeError:
        # Some backends may not accept arbitrary kwargs (like context=...).
        out = llm.generate(prompt + "\n\nContext:\n" + json.dumps(payload, indent=2))
    print(out)


if __name__ == "__main__":
    main()
