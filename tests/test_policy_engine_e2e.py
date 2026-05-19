from __future__ import annotations

from typing import Any, Dict, Optional, Type

import pytest

import llm_router
from llm_router.base import LLMBackend
from llm_router.policies.engine import RequestPolicyEngine
from llm_router.policies.privacy_guard import PrivacyGuard
from llm_router.privacy import PrivacyVault
from llm_router.router import LLMInterface
from llm_router.telemetry.benchmark_store import BenchmarkStore


class CloudBackendThatReturnsPlaceholders(LLMBackend):
    name = "openai_standard"
    last_prompt: Optional[str] = None
    last_kwargs: Dict[str, Any] = {}

    @classmethod
    def available(cls) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        type(self).last_prompt = prompt
        type(self).last_kwargs = dict(kwargs)
        # Simulate a backend that just echoes placeholders back in the response.
        return "Contact: <EMAIL_ADDRESS_1>"


@pytest.fixture
def placeholder_cloud_backend(monkeypatch: pytest.MonkeyPatch) -> Type[LLMBackend]:
    original = list(llm_router.REGISTERED_BACKENDS)
    llm_router.REGISTERED_BACKENDS.clear()
    llm_router.REGISTERED_BACKENDS.append(CloudBackendThatReturnsPlaceholders)
    yield CloudBackendThatReturnsPlaceholders
    llm_router.REGISTERED_BACKENDS.clear()
    llm_router.REGISTERED_BACKENDS.extend(original)


def test_hybrid_redacted_rehydrates_allowed_entities_end_to_end(placeholder_cloud_backend) -> None:
    engine = RequestPolicyEngine(
        privacy_guard=PrivacyGuard(vault=PrivacyVault(use_presidio=False)),
        benchmark_store=BenchmarkStore(),
        privacy_first=True,
        privacy_profile="default",
    )
    llm = LLMInterface(
        policy_engine=engine,
        privacy_first=True,
        fallback_cloud_provider="openai_standard",
        privacy_profile="default",
    )

    response = llm.generate("My email is bob@example.com. Draft a short reply.")

    assert llm.routing_plan() is not None
    assert llm.routing_plan()["execution_mode"] == "hybrid_redacted"
    assert llm.routing_plan()["provider"] == "openai_standard"
    assert placeholder_cloud_backend.last_prompt is not None
    assert "<EMAIL_ADDRESS_1>" in placeholder_cloud_backend.last_prompt
    assert "bob@example.com" not in placeholder_cloud_backend.last_prompt
    assert response == "Contact: bob@example.com"

