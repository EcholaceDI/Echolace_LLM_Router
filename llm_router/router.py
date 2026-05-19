# router.py

from contextlib import contextmanager
from functools import lru_cache
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from . import REGISTERED_BACKENDS
from .base import LLMBackend
from .diagnostics import (
    get_default_benchmark_store,
    get_default_hardware_monitor,
    get_routing_events,
    heal as diagnostics_heal,
    record_routing_decision,
    scan as diagnostic_scan,
)
from .policies import RequestPolicyEngine, RoutePlan


LOCAL_BACKENDS = ("ollama", "gguf", "hf_local", "gpt4all", "lmstudio")


class LLMInterface:
    """
    Unified interface for all LLM backends in Echolace.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        privacy_first: bool = False,
        hardware_adaptive: bool = False,
        intent_routing: bool = False,
        local_privacy_backend: str = "ollama",
        local_privacy_model: Optional[str] = None,
        fallback_cloud_provider: str = "openai_standard",
        fallback_cloud_model: str = "gpt-4o-mini",
        privacy_profile: str = "default",
        intent_schema: Optional[str] = None,
        policy_engine: Optional[RequestPolicyEngine] = None,
        start_hardware_monitor: bool = False,
        hardware_monitor_interval: int = 5,
        **kwargs: Any
    ):
        self.provider_override = provider.lower() if provider else None
        self.model_override = model
        self.init_kwargs = kwargs

        self.privacy_first = privacy_first
        self.hardware_adaptive = hardware_adaptive
        self.intent_routing = intent_routing
        self.privacy_profile = privacy_profile

        self.local_privacy_backend = local_privacy_backend.lower()
        self.local_privacy_model = local_privacy_model
        self.fallback_cloud_provider = fallback_cloud_provider.lower()
        self.fallback_cloud_model = fallback_cloud_model
        self.intent_schema = intent_schema

        self.benchmark_store = get_default_benchmark_store()
        self.hardware_monitor = get_default_hardware_monitor()
        if start_hardware_monitor:
            self.hardware_monitor.start_background(hardware_monitor_interval)

        self.policy_engine = policy_engine or RequestPolicyEngine(
            hardware_monitor=self.hardware_monitor,
            benchmark_store=self.benchmark_store,
            privacy_first=privacy_first,
            intent_routing=intent_routing,
            hardware_adaptive=hardware_adaptive,
            privacy_profile=privacy_profile,
            intent_schema=intent_schema,
        )

        self.backend: Optional[LLMBackend] = None
        self._active_provider: Optional[str] = None
        self._active_model: Optional[str] = None
        self._last_route_plan: Optional[RoutePlan] = None

        self._select_backend()
        assert self.backend is not None

    # ---------------------------------------------------------
    # Backend Selection
    # ---------------------------------------------------------
    def _select_backend(self) -> None:
        provider, model = self._baseline_backend_choice()
        self._activate_backend(provider, model)

    def _baseline_backend_choice(self) -> Tuple[str, Optional[str]]:
        if self.provider_override:
            return self.provider_override, self.model_override

        backend_cls = _get_default_backend_cls()
        if backend_cls is not None:
            return backend_cls.name, self.model_override

        return "heuristic", self.model_override

    def _activate_backend(
        self,
        provider: str,
        model: Optional[str] = None,
    ) -> LLMBackend:
        backend_cls = self._find_backend(provider)
        if backend_cls is None:
            from .providers.hf_local_backend import HeuristicBackend

            backend_cls = HeuristicBackend
            provider = backend_cls.name

        backend = backend_cls(model=model, **self.init_kwargs)
        self.backend = backend
        self._active_provider = provider
        self._active_model = model
        return backend

    @staticmethod
    def _find_backend(provider: str):
        provider = provider.lower()
        for backend in REGISTERED_BACKENDS:
            if backend.name.lower() == provider and backend.available():
                return backend
        if provider == "heuristic":
            from .providers.hf_local_backend import HeuristicBackend

            return HeuristicBackend
        return None

    def _resolve_backend(
        self,
        provider: str,
        model: Optional[str] = None,
    ) -> LLMBackend:
        if (
            self.backend is not None
            and self._active_provider == provider
            and self._active_model == model
        ):
            return self.backend
        return self._activate_backend(provider, model)

    def _available_backend_names(self) -> List[str]:
        return [
            backend.name
            for backend in REGISTERED_BACKENDS
            if backend.available()
        ]

    def _select_local_backend(
        self,
        preferred_provider: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        candidates = []
        if preferred_provider:
            candidates.append(preferred_provider.lower())
        candidates.extend(
            provider for provider in LOCAL_BACKENDS
            if provider not in candidates
        )

        for provider in candidates:
            backend_cls = self._find_backend(provider)
            if backend_cls is None:
                continue
            return provider, self._default_model_for_provider(provider)
        return None, None

    def _select_cloud_backend(
        self,
        preferred_provider: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        preferred = []
        if preferred_provider and preferred_provider not in LOCAL_BACKENDS:
            preferred.append(preferred_provider)
        preferred.extend(
            [
                self.fallback_cloud_provider,
                "openai_standard",
                "openai_universal",
                "anthropic",
                "google",
                "hf_api",
            ]
        )

        seen = set()
        for provider in preferred:
            if provider in seen:
                continue
            seen.add(provider)
            backend_cls = self._find_backend(provider)
            if backend_cls is None:
                continue
            model = self._default_model_for_provider(provider)
            if provider == self.fallback_cloud_provider:
                model = self.fallback_cloud_model
            return provider, model
        return None, None

    def _default_model_for_provider(self, provider: str) -> Optional[str]:
        provider = provider.lower()
        if provider == "ollama":
            return self.local_privacy_model or os.getenv("OLLAMA_MODEL") or "phi3"
        if provider == "gguf":
            return self.local_privacy_model or os.getenv("GGUF_MODEL_PATH")
        if provider == "hf_local":
            return os.getenv("HF_LOCAL_MODEL")
        if provider == "anthropic":
            return "claude-3-5-sonnet-latest"
        if provider in ("openai_standard", "openai_streaming"):
            return self.fallback_cloud_model
        if provider == "openai_universal":
            return os.getenv("UNIVERSAL_OPENAI_MODEL", self.fallback_cloud_model)
        return self.model_override

    def _build_route_plan(self, prompt: str) -> RoutePlan:
        baseline_provider, baseline_model = self._baseline_backend_choice()
        local_provider, local_model = self._select_local_backend(
            self.local_privacy_backend
        )
        cloud_provider, cloud_model = self._select_cloud_backend(
            preferred_provider=baseline_provider,
        )
        plan = self.policy_engine.plan_request(
            prompt=prompt,
            available_backends=self._available_backend_names(),
            provider_override=self.provider_override,
            model_override=self.model_override,
            local_provider=local_provider,
            local_model=local_model,
            cloud_provider=cloud_provider or baseline_provider,
            cloud_model=cloud_model or baseline_model,
        )
        self._last_route_plan = plan

        record_routing_decision(
            stage="plan",
            reason="request_policy_engine",
            selected_provider=plan.provider,
            selected_model=plan.model,
            original_provider=baseline_provider,
            overridden=(plan.provider != baseline_provider or plan.model != baseline_model),
            metadata=plan.to_dict(),
        )
        if plan.provider == "blocked":
            raise RuntimeError(
                "Privacy policy requires strict local execution, but no local "
                "backend is currently available."
            )
        return plan

    def _token_count(self, text: str) -> int:
        return len(text.split())

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def generate(self, prompt: str, **kwargs: Any) -> str:
        plan = self._build_route_plan(prompt)
        backend = self._resolve_backend(plan.provider, plan.model)

        started_token = self.benchmark_store.start_request(plan.provider)
        started_at = time.perf_counter()
        try:
            raw_response = backend.generate(plan.prompt, **kwargs)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            self.benchmark_store.finish_request(
                backend=plan.provider,
                started_at=started_token,
                duration_ms=duration_ms,
                token_count=0,
                ttft_ms=duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - started_at) * 1000.0

        response = self.policy_engine.finalize_response(raw_response, plan)
        self.benchmark_store.finish_request(
            backend=plan.provider,
            started_at=started_token,
            duration_ms=duration_ms,
            token_count=self._token_count(response),
            ttft_ms=duration_ms,
        )
        record_routing_decision(
            stage="generate",
            reason="request_completed",
            selected_provider=plan.provider,
            selected_model=plan.model,
            original_provider=self.provider_override or plan.provider,
            overridden=False,
            metadata={
                "duration_ms": round(duration_ms, 4),
                "execution_mode": plan.execution_mode,
            },
        )
        return response

    def stream(self, prompt: str, **kwargs: Any):
        plan = self._build_route_plan(prompt)
        backend = self._resolve_backend(plan.provider, plan.model)

        if plan.execution_mode == "hybrid_redacted":
            text = self.generate(prompt, **kwargs)
            import re

            for word in re.split(r"(\s+)", text):
                if word:
                    yield {"token": word, "raw": None}
            return

        started_token = self.benchmark_store.start_request(plan.provider)
        started_at = time.perf_counter()
        first_token_ms: Optional[float] = None
        token_count = 0
        collected: List[str] = []

        if hasattr(backend, "stream"):
            try:
                for chunk in backend.stream(plan.prompt, **kwargs):
                    now_ms = (time.perf_counter() - started_at) * 1000.0
                    if first_token_ms is None:
                        first_token_ms = now_ms
                    token = chunk.get("token", "")
                    if token:
                        token_count += max(1, len(token.split()))
                        collected.append(token)
                    yield chunk
                duration_ms = (time.perf_counter() - started_at) * 1000.0
                self.benchmark_store.finish_request(
                    backend=plan.provider,
                    started_at=started_token,
                    duration_ms=duration_ms,
                    token_count=token_count,
                    ttft_ms=first_token_ms,
                )
                record_routing_decision(
                    stage="stream",
                    reason="stream_completed",
                    selected_provider=plan.provider,
                    selected_model=plan.model,
                    original_provider=self.provider_override or plan.provider,
                    overridden=False,
                    metadata={
                        "duration_ms": round(duration_ms, 4),
                        "ttft_ms": round(first_token_ms or duration_ms, 4),
                    },
                )
                return
            except Exception:
                duration_ms = (time.perf_counter() - started_at) * 1000.0
                self.benchmark_store.finish_request(
                    backend=plan.provider,
                    started_at=started_token,
                    duration_ms=duration_ms,
                    token_count=token_count,
                    ttft_ms=first_token_ms or duration_ms,
                )
                raise
            except NotImplementedError:
                pass

        try:
            text = backend.generate(plan.prompt, **kwargs)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            self.benchmark_store.finish_request(
                backend=plan.provider,
                started_at=started_token,
                duration_ms=duration_ms,
                token_count=token_count,
                ttft_ms=first_token_ms or duration_ms,
            )
            raise
        response = self.policy_engine.finalize_response(text, plan)
        import re

        for word in re.split(r"(\s+)", response):
            if word:
                yield {"token": word, "raw": None}

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self.benchmark_store.finish_request(
            backend=plan.provider,
            started_at=started_token,
            duration_ms=duration_ms,
            token_count=self._token_count(response),
            ttft_ms=duration_ms,
        )
        record_routing_decision(
            stage="stream",
            reason="stream_emulated",
            selected_provider=plan.provider,
            selected_model=plan.model,
            original_provider=self.provider_override or plan.provider,
            overridden=False,
            metadata={"duration_ms": round(duration_ms, 4)},
        )

    def diagnostics(self) -> Dict[str, Any]:
        report = diagnostic_scan()
        report["selected_backend"] = self.current_backend()
        report["selected_model"] = self._active_model
        report["last_route_plan"] = (
            self._last_route_plan.to_dict() if self._last_route_plan is not None else None
        )
        return report

    def heal(
        self,
        apply: bool = False,
        allow_network: bool = False,
        install_python_deps: bool = False,
        pull_models: bool = False,
        prefer_local: bool = True,
        backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        return diagnostics_heal(
            apply=apply,
            allow_network=allow_network,
            install_python_deps=install_python_deps,
            pull_models=pull_models,
            prefer_local=prefer_local,
            backend=backend,
        )

    def intent(
        self,
        prompt: str,
        top_k: int = 3,
        include_route: bool = True,
        schema_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        decision = self.policy_engine.intent_router.recommend(
            prompt,
            top_k=top_k,
            schema_name=schema_name or self.intent_schema,
        )
        payload = decision.to_dict()
        if not include_route:
            payload.pop("recommended_provider", None)
            payload.pop("recommended_backend", None)
            payload.pop("recommended_model", None)
        return payload

    def hardware_status(self) -> Dict[str, Any]:
        return self.hardware_monitor.current()

    def privacy_status(self) -> Optional[Dict[str, Any]]:
        if self._last_route_plan is None:
            return None
        return self._last_route_plan.privacy.to_dict()

    def routing_plan(self) -> Optional[Dict[str, Any]]:
        if self._last_route_plan is None:
            return None
        return self._last_route_plan.to_dict()

    def available_backends(self) -> List[str]:
        return self._available_backend_names()

    def current_backend(self) -> str:
        return getattr(self.backend, "name", "unknown")

    def best_backend(self) -> Optional[str]:
        cls = _get_default_backend_cls()
        return cls.name if cls else None

    def routing_events(self) -> List[Dict[str, Any]]:
        return get_routing_events()

    # ---------------------------------------------------------
    # Runtime Switching
    # ---------------------------------------------------------
    def switch(self, provider: str, model: Optional[str] = None) -> bool:
        backend_cls = self._find_backend(provider.lower())
        if backend_cls:
            self.provider_override = provider.lower()
            self.model_override = model or self.model_override
            self._activate_backend(provider.lower(), self.model_override)
            return True
        return False

    @contextmanager
    def use_backend(self, provider: str, model: Optional[str] = None):
        original_provider = self.provider_override
        original_model = self.model_override
        original_backend = self.backend
        original_active_provider = self._active_provider
        original_active_model = self._active_model

        if not self.switch(provider, model=model):
            raise ValueError(f"Backend '{provider}' not available.")

        try:
            yield self
        finally:
            self.provider_override = original_provider
            self.model_override = original_model
            self.backend = original_backend
            self._active_provider = original_active_provider
            self._active_model = original_active_model

    def __call__(self, prompt: str, **kwargs: Any) -> str:
        return self.generate(prompt, **kwargs)

    def __repr__(self) -> str:
        return f"<LLMInterface backend={self.current_backend()}>"

    def info(self) -> Dict[str, Any]:
        return {
            "backend": self.current_backend(),
            "selected_model": self._active_model,
            "available_backends": self.available_backends(),
            "best_backend": self.best_backend(),
            "privacy_first": self.privacy_first,
            "hardware_adaptive": self.hardware_adaptive,
            "intent_routing": self.intent_routing,
            "privacy_profile": self.privacy_profile,
            "intent_schema": self.intent_schema,
        }


@lru_cache(maxsize=1)
def _get_default_backend_cls():
    for backend in REGISTERED_BACKENDS:
        if backend.available():
            return backend
    return None
