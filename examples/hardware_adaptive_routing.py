#!/usr/bin/env python3
"""
Hardware-adaptive routing demo (Echolace LLM Router).

This script demonstrates:
- Hardware status snapshot
- Backend selection behavior when hardware_adaptive=True
- Recording of routing decisions in routing_events()

Run from project root:
  python examples/hardware_adaptive_routing.py
"""

from __future__ import annotations

import json
import time

from llm_router import LLMInterface


def main() -> None:
    llm = LLMInterface(
        hardware_adaptive=True,
        start_hardware_monitor=True,
        hardware_monitor_interval=2,
    )

    print("== Hardware status (initial) ==")
    print(json.dumps(llm.hardware_status(), indent=2, sort_keys=True))

    print("\nWaiting a few seconds to gather telemetry...")
    time.sleep(5)

    print("\n== Hardware status (after sampling) ==")
    print(json.dumps(llm.hardware_status(), indent=2, sort_keys=True))

    prompt = "In one sentence: what is the purpose of an LLM router?"
    print("\n== Generate (hardware-adaptive) ==")
    try:
        out = llm.generate(prompt)
        print(out)
    except Exception as exc:
        print(f"Generation failed (likely no configured backend credentials): {exc}")

    print("\n== Recent routing events ==")
    events = llm.routing_events()
    print(json.dumps(events[-10:], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
