from typing import Any, List, Optional

from ..telemetry import BenchmarkStore, HardwareMonitor
from .intent_router import IntentRouter
from .privacy_guard import PrivacyGuard
from .route_planner import RoutePlan, RoutePlanner

LOCAL_BACKENDS = {"ollama", "gguf", "hf_local", "gpt4all", "lmstudio"}


class RequestPolicyEngine:
    def __init__(
        self,
        privacy_guard: Optional[PrivacyGuard] = None,
        intent_router: Optional[IntentRouter] = None,
        route_planner: Optional[RoutePlanner] = None,
        hardware_monitor: Optional[HardwareMonitor] = None,
        benchmark_store: Optional[BenchmarkStore] = None,
        privacy_first: bool = False,
        intent_routing: bool = False,
        hardware_adaptive: bool = False,
        privacy_profile: str = "default",
        intent_schema: Optional[str] = None,
    ):
        self.benchmark_store = benchmark_store or BenchmarkStore()
        self.hardware_monitor = hardware_monitor or HardwareMonitor(
            benchmark_store=self.benchmark_store
        )
        self.privacy_guard = privacy_guard or PrivacyGuard()
        self.intent_router = intent_router or IntentRouter(schema_name=intent_schema)
        self.route_planner = route_planner or RoutePlanner()
        self.privacy_first = privacy_first
        self.intent_routing = intent_routing
        self.hardware_adaptive = hardware_adaptive
        self.privacy_profile = privacy_profile
        self.intent_schema = intent_schema

    def plan_request(
        self,
        prompt: Any,
        available_backends: List[str],
        provider_override: Optional[str],
        model_override: Optional[str],
        local_provider: Optional[str],
        local_model: Optional[str],
        cloud_provider: Optional[str],
        cloud_model: Optional[str],
    ) -> RoutePlan:
        privacy = self.privacy_guard.evaluate(
            prompt,
            enabled=self.privacy_first,
            profile_name=self.privacy_profile,
        )
        intent_prompt = self.privacy_guard.vault.inspector.extract_text(prompt)
        if self.intent_schema:
            intent = self.intent_router.recommend(
                intent_prompt,
                schema_name=self.intent_schema,
            )
        else:
            intent = self.intent_router.recommend(intent_prompt)
        hardware_status = self.hardware_monitor.sample() if self.hardware_adaptive else self.hardware_monitor.current()
        hardware_status["local_viability"] = {}
        local_candidates = []
        if local_provider:
            local_candidates.append(local_provider)
        local_candidates.extend(
            backend
            for backend in available_backends
            if backend in LOCAL_BACKENDS and backend not in local_candidates
        )
        privacy_priority = (
            1.0
            if privacy.execution_mode == "strict_local"
            else 0.5 if privacy.execution_mode == "hybrid_redacted" else 0.0
        )
        for candidate in local_candidates:
            hardware_status["local_viability"][candidate] = self.hardware_monitor.local_viability(
                candidate,
                privacy_priority=privacy_priority,
            )
        hardware_status["downgrade_recommendations"] = {}
        for candidate in local_candidates:
            if hasattr(self.hardware_monitor, "downgrade_decision"):
                hardware_status["downgrade_recommendations"][candidate] = self.hardware_monitor.downgrade_decision(
                    candidate,
                    available_backends,
                    cloud_provider=cloud_provider,
                    strict_local=privacy.execution_mode == "strict_local",
                )
            else:
                hardware_status["downgrade_recommendations"][candidate] = {
                    "action": "keep",
                    "target_provider": candidate,
                    "target_model": None,
                }
        benchmark_summary = self.benchmark_store.summary()

        if not self.intent_routing and not provider_override and privacy.execution_mode == "cloud_allowed":
            intent.recommended_provider = cloud_provider or intent.recommended_provider
            intent.recommended_model = cloud_model or intent.recommended_model

        return self.route_planner.plan(
            available_backends=available_backends,
            provider_override=provider_override,
            model_override=model_override,
            privacy_decision=privacy,
            intent_decision=intent,
            hardware_status=hardware_status,
            benchmark_summary=benchmark_summary,
            local_provider=local_provider,
            local_model=local_model,
            cloud_provider=cloud_provider,
            cloud_model=cloud_model,
        )

    def finalize_response(self, response: str, plan: RoutePlan) -> str:
        return self.privacy_guard.postprocess_response(response, plan.privacy)
