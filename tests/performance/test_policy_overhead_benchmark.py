from __future__ import annotations

from typing import Any, Dict, List

import pytest

from llm_router.policies.engine import RequestPolicyEngine
from llm_router.policies.intent_router import IntentDecision
from llm_router.policies.intent_router import IntentRouter as RealIntentRouter
from llm_router.policies.privacy_guard import PrivacyGuard
from llm_router.privacy import PrivacyVault
from llm_router.telemetry.benchmark_store import BenchmarkStore


class FastIntentRouter(RealIntentRouter):
    def recommend(
        self, prompt: str, top_k: int = 3, schema_name: str | None = None
    ) -> IntentDecision:
        return IntentDecision(
            label="SIMPLE",
            confidence=0.9,
            candidate_labels=["SIMPLE"],
            recommended_provider="openai_standard",
            recommended_model="gpt-4o-mini",
            source="benchmark",
            raw={},
        )


class FastHardwareMonitor:
    def sample(self) -> Dict[str, Any]:
        return self.current()

    def current(self) -> Dict[str, Any]:
        return {
            "cpu": {"utilization_percent": 10.0},
            "memory": {"utilization_percent": 20.0},
            "gpu": {"utilization_percent": 0.0},
            "thermal_throttling": False,
            "should_offload": False,
        }

    def local_viability(self, backend: str, privacy_priority: float = 0.0) -> float:
        return 0.9


@pytest.mark.benchmark(group="policy_engine")
def test_policy_engine_plan_request_overhead(benchmark) -> None:
    guard = PrivacyGuard(vault=PrivacyVault(use_presidio=False))
    engine = RequestPolicyEngine(
        privacy_guard=guard,
        intent_router=FastIntentRouter(schema_name=None),
        benchmark_store=BenchmarkStore(),
        hardware_monitor=FastHardwareMonitor(),
        privacy_first=True,
        intent_routing=True,
        hardware_adaptive=True,
        privacy_profile="default",
    )
    available_backends: List[str] = ["openai_standard", "ollama"]

    def run() -> None:
        engine.plan_request(
            prompt="Email me at bob@example.com about the meeting.",
            available_backends=available_backends,
            provider_override=None,
            model_override=None,
            local_provider="ollama",
            local_model=None,
            cloud_provider="openai_standard",
            cloud_model="gpt-4o-mini",
        )

    benchmark(run)
