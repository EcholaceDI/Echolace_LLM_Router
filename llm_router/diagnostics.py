# diagnostics.py

import json
import os
import platform
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Type

from . import REGISTERED_BACKENDS
from .base import LLMBackend
from .healing import HealingPlanner
from .telemetry import BenchmarkStore, HardwareMonitor

_ROUTING_EVENTS: Deque[Dict[str, Any]] = deque(maxlen=500)
_DEFAULT_BENCHMARK_STORE = BenchmarkStore()
_DEFAULT_HARDWARE_MONITOR = HardwareMonitor(benchmark_store=_DEFAULT_BENCHMARK_STORE)
_DEFAULT_HEALING_PLANNER = HealingPlanner()


def get_default_benchmark_store() -> BenchmarkStore:
    return _DEFAULT_BENCHMARK_STORE


def get_default_hardware_monitor() -> HardwareMonitor:
    return _DEFAULT_HARDWARE_MONITOR


def record_routing_decision(
    stage: str,
    reason: str,
    selected_provider: str,
    selected_model: Optional[str] = None,
    original_provider: Optional[str] = None,
    overridden: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = {
        "timestamp": time.time(),
        "stage": stage,
        "reason": reason,
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "original_provider": original_provider,
        "overridden": overridden,
        "metadata": metadata or {},
    }
    _ROUTING_EVENTS.append(event)
    return event


def get_routing_events() -> List[Dict[str, Any]]:
    return list(_ROUTING_EVENTS)


def record_benchmark(
    backend: str,
    started_at: float,
    duration_ms: float,
    token_count: int,
    ttft_ms: Optional[float] = None,
) -> None:
    _DEFAULT_BENCHMARK_STORE.finish_request(
        backend=backend,
        started_at=started_at,
        duration_ms=duration_ms,
        token_count=token_count,
        ttft_ms=ttft_ms,
    )


def _env_summary() -> Dict[str, Any]:
    return {
        "OPENAI_API_KEY": "SET" if os.getenv("OPENAI_API_KEY") else "NONE",
        "ANTHROPIC_API_KEY": "SET" if os.getenv("ANTHROPIC_API_KEY") else "NONE",
        "GOOGLE_API_KEY": "SET" if os.getenv("GOOGLE_API_KEY") else "NONE",
        "HUGGINGFACE_API_KEY": (
            "SET"
            if (os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_API_KEY"))
            else "NONE"
        ),
        "HF_LOCAL_MODEL": os.getenv("HF_LOCAL_MODEL") or "NONE",
        "GGUF_MODEL_PATH": os.getenv("GGUF_MODEL_PATH") or "NONE",
        "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL") or "NONE",
    }


def _backend_status(backend: Type[LLMBackend]) -> Dict[str, Any]:
    try:
        available = backend.available()
        diag = backend.diagnose()
    except Exception as exc:
        diag = {"error": str(exc)}
        available = False

    return {
        "name": backend.name,
        "available": available,
        "diagnostics": diag,
        "benchmark": _DEFAULT_BENCHMARK_STORE.summary(backend.name),
    }


def scan() -> Dict[str, Any]:
    backends = [_backend_status(backend) for backend in REGISTERED_BACKENDS]
    actions = _DEFAULT_HEALING_PLANNER.plan(backends)
    return {
        "platform": {
            "os": platform.system(),
            "version": platform.version(),
            "python": platform.python_version(),
        },
        "environment": _env_summary(),
        "hardware": _DEFAULT_HARDWARE_MONITOR.current(),
        "benchmark_store": _DEFAULT_BENCHMARK_STORE.summary(),
        "backends": backends,
        "routing_events": get_routing_events(),
        "actionable_status": {
            "healthy": any(backend["available"] for backend in backends),
            "available_backends": sum(
                1 for backend in backends if backend["available"]
            ),
            "recommended_actions": actions,
        },
    }


def heal(
    apply: bool = False,
    allow_network: bool = False,
    install_python_deps: bool = False,
    pull_models: bool = False,
    prefer_local: bool = True,
    backend: Optional[str] = None,
) -> Dict[str, Any]:
    report = scan()
    backends = report["backends"]
    if backend:
        backends = [item for item in backends if item["name"] == backend]
    plan = _DEFAULT_HEALING_PLANNER.plan(backends, prefer_local=prefer_local)
    results = {"applied": [], "skipped": plan, "failed": []}
    if apply:
        results = _DEFAULT_HEALING_PLANNER.apply(
            plan,
            allow_network=allow_network,
            install_python_deps=install_python_deps,
            pull_models=pull_models,
        )
    prompts = [
        {
            "backend": action.get("backend"),
            "prompt": action.get("prompt"),
            "title": action.get("title"),
        }
        for action in plan
        if action.get("prompt")
    ]
    return {
        "healthy": report["actionable_status"]["healthy"],
        "selected_backend": backend,
        "issues": plan,
        "plan": plan,
        "applied": results["applied"],
        "skipped": results["skipped"],
        "failed": results.get("failed", []),
        "prompts": prompts,
        "hardware": report["hardware"],
    }


def pretty_print() -> None:
    print(json.dumps(scan(), indent=2, ensure_ascii=False))


def json_report() -> str:
    return json.dumps(scan(), indent=2, ensure_ascii=False)
