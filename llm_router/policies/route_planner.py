from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .intent_router import IntentDecision
from .privacy_guard import PrivacyDecision

LOCAL_BACKENDS = {"ollama", "gguf", "hf_local", "gpt4all", "lmstudio"}


@dataclass
class RoutePlan:
    provider: str
    model: Optional[str]
    prompt: Any
    execution_mode: str
    privacy: PrivacyDecision
    intent: IntentDecision
    hardware_status: Dict[str, Any]
    benchmark_summary: Dict[str, Any]
    audit_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt": self.prompt,
            "execution_mode": self.execution_mode,
            "privacy": self.privacy.to_dict(),
            "intent": self.intent.to_dict(),
            "hardware_status": self.hardware_status,
            "benchmark_summary": self.benchmark_summary,
            "audit_metadata": self.audit_metadata,
        }


class RoutePlanner:
    def plan(
        self,
        available_backends: List[str],
        provider_override: Optional[str],
        model_override: Optional[str],
        privacy_decision: PrivacyDecision,
        intent_decision: IntentDecision,
        hardware_status: Dict[str, Any],
        benchmark_summary: Dict[str, Any],
        local_provider: Optional[str],
        local_model: Optional[str],
        cloud_provider: Optional[str],
        cloud_model: Optional[str],
    ) -> RoutePlan:
        provider = provider_override or cloud_provider or "heuristic"
        model = model_override or cloud_model
        prompt = privacy_decision.prompt_for_local
        local_viability = hardware_status.get("local_viability", {})
        downgrade_recommendations = hardware_status.get("downgrade_recommendations", {})

        if privacy_decision.execution_mode == "strict_local":
            if local_provider is None:
                provider = "blocked"
                model = None
            else:
                provider = local_provider
                model = local_model or model
            prompt = privacy_decision.prompt_for_local
        elif privacy_decision.execution_mode == "hybrid_redacted":
            if cloud_provider:
                provider = cloud_provider
                model = cloud_model or model
            elif local_provider:
                provider = local_provider
                model = local_model or model
            prompt = privacy_decision.prompt_for_cloud
        elif (
            not provider_override
            and intent_decision.recommended_provider in available_backends
        ):
            provider = intent_decision.recommended_provider
            model = intent_decision.recommended_model or model

        viability = local_viability.get(provider)
        downgrade = downgrade_recommendations.get(provider, {})
        if provider in LOCAL_BACKENDS and (
            hardware_status.get("should_offload")
            or (viability is not None and viability < 0.35)
        ):
            action = downgrade.get("action")
            if action == "downgrade_local":
                provider = downgrade.get("target_provider", provider)
                model = downgrade.get("target_model") or local_model or model
                prompt = privacy_decision.prompt_for_local
            elif (
                action == "offload_cloud"
                and privacy_decision.execution_mode != "strict_local"
            ):
                provider = (
                    downgrade.get("target_provider") or cloud_provider or provider
                )
                model = downgrade.get("target_model") or cloud_model or model
                prompt = (
                    privacy_decision.prompt_for_cloud
                    if privacy_decision.execution_mode == "hybrid_redacted"
                    else privacy_decision.prompt_for_local
                )
            elif privacy_decision.execution_mode != "strict_local" and cloud_provider:
                provider = cloud_provider
                model = cloud_model or model
                prompt = (
                    privacy_decision.prompt_for_cloud
                    if privacy_decision.execution_mode == "hybrid_redacted"
                    else privacy_decision.prompt_for_local
                )

        return RoutePlan(
            provider=provider,
            model=model,
            prompt=prompt,
            execution_mode=privacy_decision.execution_mode,
            privacy=privacy_decision,
            intent=intent_decision,
            hardware_status=hardware_status,
            benchmark_summary=benchmark_summary,
            audit_metadata={
                "execution_mode": privacy_decision.execution_mode,
                "privacy_profile": privacy_decision.profile,
                "intent_label": intent_decision.label,
                "hardware_offload": hardware_status.get("should_offload", False),
                "downgrade_action": downgrade.get("action"),
                "downgrade_target": downgrade.get("target_provider"),
                "local_viability": viability,
            },
        )
