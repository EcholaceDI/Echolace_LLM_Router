from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

import pytest

import llm_router
from llm_router.base import LLMBackend
from llm_router.policies.engine import RequestPolicyEngine
from llm_router.policies.privacy_guard import PrivacyGuard
from llm_router.privacy import PrivacyVault
from llm_router.router import LLMInterface
from llm_router.telemetry.benchmark_store import BenchmarkStore


class FakeCloudBackend(LLMBackend):
    name = "openai_standard"
    last_prompt: Optional[str] = None
    last_kwargs: Dict[str, Any] = {}

    @classmethod
    def available(cls) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        type(self).last_prompt = prompt
        type(self).last_kwargs = dict(kwargs)
        return "CLOUD_RESPONSE:" + prompt


class FakeLocalBackend(LLMBackend):
    name = "ollama"
    last_prompt: Optional[str] = None

    @classmethod
    def available(cls) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        type(self).last_prompt = prompt
        return "LOCAL_RESPONSE:" + prompt


@pytest.fixture
def fake_backends(monkeypatch: pytest.MonkeyPatch) -> List[Type[LLMBackend]]:
    original = list(llm_router.REGISTERED_BACKENDS)
    llm_router.REGISTERED_BACKENDS.clear()
    llm_router.REGISTERED_BACKENDS.extend([FakeLocalBackend, FakeCloudBackend])
    yield llm_router.REGISTERED_BACKENDS
    llm_router.REGISTERED_BACKENDS.clear()
    llm_router.REGISTERED_BACKENDS.extend(original)


def build_engine(
    *,
    privacy_first: bool,
    privacy_profile: str = "default",
) -> RequestPolicyEngine:
    guard = PrivacyGuard(vault=PrivacyVault(use_presidio=False))
    return RequestPolicyEngine(
        privacy_guard=guard,
        benchmark_store=BenchmarkStore(),
        privacy_first=privacy_first,
        privacy_profile=privacy_profile,
    )


def test_hybrid_redacted_cloud_backend_receives_redacted_prompt(fake_backends) -> None:
    engine = build_engine(privacy_first=True, privacy_profile="default")
    llm = LLMInterface(
        policy_engine=engine,
        privacy_first=True,
        fallback_cloud_provider="openai_standard",
    )

    response = llm.generate("Email me at bob@example.com about the report.")

    assert llm.routing_plan() is not None
    assert llm.routing_plan()["execution_mode"] == "hybrid_redacted"
    assert llm.routing_plan()["provider"] == "openai_standard"
    assert FakeCloudBackend.last_prompt is not None
    assert "<EMAIL_ADDRESS_1>" in FakeCloudBackend.last_prompt
    assert "bob@example.com" not in FakeCloudBackend.last_prompt
    assert "bob@example.com" in response


def test_strict_local_blocks_cloud_and_uses_local_backend(fake_backends) -> None:
    engine = build_engine(privacy_first=True, privacy_profile="hipaa")
    llm = LLMInterface(
        policy_engine=engine,
        privacy_first=True,
        local_privacy_backend="ollama",
        fallback_cloud_provider="openai_standard",
        privacy_profile="hipaa",
    )

    response = llm.generate("Patient email is bob@example.com.")

    assert llm.routing_plan() is not None
    assert llm.routing_plan()["execution_mode"] == "strict_local"
    assert llm.routing_plan()["provider"] == "ollama"
    assert FakeLocalBackend.last_prompt == "Patient email is bob@example.com."
    assert response.startswith("LOCAL_RESPONSE:")


def test_cloud_allowed_routes_to_cloud_when_privacy_disabled(fake_backends) -> None:
    engine = build_engine(privacy_first=False)
    llm = LLMInterface(
        policy_engine=engine,
        privacy_first=False,
        fallback_cloud_provider="openai_standard",
    )

    response = llm.generate("Hello there.")

    assert llm.routing_plan() is not None
    assert llm.routing_plan()["execution_mode"] == "cloud_allowed"
    assert llm.routing_plan()["provider"] == "openai_standard"
    assert FakeCloudBackend.last_prompt == "Hello there."
    assert response.startswith("CLOUD_RESPONSE:")
