from typing import Any, Dict, List, Optional

import pytest

from llm_router.base import LLMBackend
from llm_router.policies.engine import RequestPolicyEngine
from llm_router.policies.intent_router import IntentDecision
from llm_router.policies.privacy_guard import PrivacyDecision, PrivacyGuard
from llm_router.policies.route_planner import RoutePlan
from llm_router.privacy import PrivacyVault
from llm_router.router import LLMInterface
from llm_router.security import PrivacyScanResult
from llm_router.telemetry.benchmark_store import BenchmarkStore


class FakeIntentRouter:
    def __init__(self, provider: str, model: str, label: str = "SIMPLE"):
        self.provider = provider
        self.model = model
        self.label = label
        self.prompts: List[str] = []

    def recommend(self, prompt: str, top_k: int = 3) -> IntentDecision:
        self.prompts.append(prompt)
        return IntentDecision(
            label=self.label,
            confidence=0.95,
            candidate_labels=[self.label],
            recommended_provider=self.provider,
            recommended_model=self.model,
            source="test",
            raw={"prompt": prompt, "top_k": top_k},
        )


class FakeHardwareMonitor:
    def __init__(self, should_offload: bool = False, viability: float = 0.9):
        self.should_offload = should_offload
        self.viability = viability

    def sample(self) -> Dict[str, Any]:
        return self.current()

    def current(self) -> Dict[str, Any]:
        return {
            "cpu": {"utilization_percent": 10.0},
            "memory": {"utilization_percent": 20.0},
            "gpu": {"utilization_percent": 5.0},
            "thermal_throttling": False,
            "should_offload": self.should_offload,
        }

    def local_viability(self, backend: str, privacy_priority: float = 0.0) -> float:
        return self.viability


class FakePolicyEngine:
    def __init__(self) -> None:
        scan_result = PrivacyScanResult(
            findings=[],
            redacted_text="sanitized prompt",
            placeholder_map={},
            entity_map={},
            redacted_payload="sanitized prompt",
            source_kind="text",
        )
        self.plan = RoutePlan(
            provider="fake",
            model=None,
            prompt="sanitized prompt",
            execution_mode="cloud_allowed",
            privacy=PrivacyDecision(
                execution_mode="cloud_allowed",
                request_id=None,
                scan_result=scan_result,
                prompt_for_cloud="sanitized prompt",
                prompt_for_local="original prompt",
                allow_rehydration=False,
                allowed_entity_types=[],
                profile="default",
            ),
            intent=IntentDecision(
                label="SIMPLE",
                confidence=0.9,
                candidate_labels=["SIMPLE"],
                recommended_provider="fake",
                recommended_model="fake-model",
                source="test",
                raw={},
            ),
            hardware_status={},
            benchmark_summary={},
            audit_metadata={},
        )

    def plan_request(self, **_: Any) -> RoutePlan:
        return self.plan

    def finalize_response(self, response: str, plan: RoutePlan) -> str:
        assert plan is self.plan
        return response.upper()


class FakeBackend(LLMBackend):
    name = "fake"
    last_prompt: Optional[str] = None

    @classmethod
    def available(cls) -> bool:
        return True

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {"status": "ok"}

    def generate(self, prompt: str, **kwargs: Any) -> str:
        type(self).last_prompt = prompt
        return "backend:" + prompt


def build_engine(
    *,
    privacy_first: bool = False,
    intent_routing: bool = False,
    hardware_adaptive: bool = False,
    intent_provider: str = "anthropic",
    intent_model: str = "claude-3-5-sonnet-latest",
    should_offload: bool = False,
    viability: float = 0.9,
) -> RequestPolicyEngine:
    return RequestPolicyEngine(
        privacy_guard=PrivacyGuard(vault=PrivacyVault(use_presidio=False)),
        intent_router=FakeIntentRouter(intent_provider, intent_model),
        hardware_monitor=FakeHardwareMonitor(
            should_offload=should_offload,
            viability=viability,
        ),
        benchmark_store=BenchmarkStore(),
        privacy_first=privacy_first,
        intent_routing=intent_routing,
        hardware_adaptive=hardware_adaptive,
    )


def test_strict_local_routing_behavior() -> None:
    engine = build_engine(privacy_first=True, intent_routing=True)

    plan = engine.plan_request(
        prompt="Patient Jane Doe has SSN 123-45-6789",
        available_backends=["ollama", "openai_standard", "anthropic"],
        provider_override=None,
        model_override=None,
        local_provider="ollama",
        local_model="phi3",
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.execution_mode == "strict_local"
    assert plan.provider == "ollama"
    assert plan.prompt == "Patient Jane Doe has SSN 123-45-6789"


def test_hybrid_redacted_routing_behavior() -> None:
    engine = build_engine(privacy_first=True, intent_routing=True)
    payload = {
        "contact": {"email": "bob@example.com"},
        "request": "Summarize the account status.",
    }

    plan = engine.plan_request(
        prompt=payload,
        available_backends=["ollama", "openai_standard", "anthropic"],
        provider_override=None,
        model_override=None,
        local_provider="ollama",
        local_model="phi3",
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.execution_mode == "hybrid_redacted"
    assert plan.provider == "openai_standard"
    assert plan.prompt["contact"]["email"] == "<EMAIL_ADDRESS_1>"
    assert plan.privacy.prompt_for_local == payload


def test_intent_based_routing_decisions() -> None:
    engine = build_engine(
        privacy_first=False,
        intent_routing=True,
        intent_provider="anthropic",
        intent_model="claude-3-5-sonnet-latest",
    )

    plan = engine.plan_request(
        prompt="Refactor this Python function and add tests.",
        available_backends=["anthropic", "openai_standard"],
        provider_override=None,
        model_override=None,
        local_provider="ollama",
        local_model="phi3",
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.execution_mode == "cloud_allowed"
    assert plan.provider == "anthropic"
    assert plan.intent.label == "SIMPLE" or plan.intent.label == "CODE"


def test_hardware_aware_routing_offloads_local_intent() -> None:
    engine = build_engine(
        privacy_first=False,
        intent_routing=True,
        hardware_adaptive=True,
        intent_provider="ollama",
        intent_model="phi3",
        should_offload=True,
        viability=0.1,
    )

    plan = engine.plan_request(
        prompt="Quick summary please.",
        available_backends=["ollama", "openai_standard"],
        provider_override=None,
        model_override=None,
        local_provider="ollama",
        local_model="phi3",
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.provider == "openai_standard"
    assert plan.audit_metadata["hardware_offload"] is True


def test_privacy_guard_prevents_unsafe_cloud_routing_without_local_backend() -> None:
    engine = build_engine(privacy_first=True, intent_routing=True)

    plan = engine.plan_request(
        prompt={"patient": {"ssn": "123-45-6789"}},
        available_backends=["openai_standard"],
        provider_override=None,
        model_override=None,
        local_provider=None,
        local_model=None,
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.execution_mode == "strict_local"
    assert plan.provider == "blocked"


def test_router_generate_uses_policy_plan_and_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_find_backend = LLMInterface._find_backend
    monkeypatch.setattr(
        LLMInterface,
        "_find_backend",
        staticmethod(lambda provider: FakeBackend if provider == "fake" else None),
    )

    llm = LLMInterface(provider="fake", policy_engine=FakePolicyEngine())
    response = llm.generate("original prompt")

    assert response == "BACKEND:SANITIZED PROMPT"
    assert FakeBackend.last_prompt == "sanitized prompt"
    assert llm.routing_plan()["provider"] == "fake"

    monkeypatch.setattr(LLMInterface, "_find_backend", original_find_backend)
