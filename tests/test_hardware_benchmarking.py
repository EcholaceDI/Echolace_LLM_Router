import sqlite3
from pathlib import Path

from llm_router.policies.intent_router import IntentDecision
from llm_router.policies.privacy_guard import PrivacyDecision
from llm_router.policies.route_planner import RoutePlanner
from llm_router.security import PrivacyScanResult
from llm_router.telemetry.benchmark_store import BenchmarkStore
from llm_router.telemetry.hardware_monitor import HardwareMonitor


def _low_pressure_hardware() -> dict:
    return {
        "cpu": {"utilization_percent": 15.0},
        "memory": {"utilization_percent": 20.0},
        "gpu": {"utilization_percent": 0.0, "memory_utilization_percent": 0.0},
        "thermal_throttling": False,
        "should_offload": False,
    }


def _offload_hardware() -> dict:
    status = _low_pressure_hardware()
    status["cpu"]["utilization_percent"] = 95.0
    status["should_offload"] = True
    return status


def _privacy_decision() -> PrivacyDecision:
    scan_result = PrivacyScanResult(
        findings=[],
        redacted_text="prompt",
        placeholder_map={},
        entity_map={},
        redacted_payload="prompt",
        source_kind="text",
    )
    return PrivacyDecision(
        execution_mode="cloud_allowed",
        request_id=None,
        scan_result=scan_result,
        prompt_for_cloud="prompt",
        prompt_for_local="prompt",
        allow_rehydration=False,
        allowed_entity_types=[],
        profile="default",
    )


def _intent_decision(provider: str, model: str = "phi3") -> IntentDecision:
    return IntentDecision(
        label="SIMPLE",
        confidence=0.9,
        candidate_labels=["SIMPLE"],
        recommended_provider=provider,
        recommended_model=model,
        source="test",
        raw={},
    )


def test_canary_benchmarks_record_metrics_and_sqlite(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "telemetry.sqlite"
    store = BenchmarkStore(sqlite_path=str(sqlite_path))
    monitor = HardwareMonitor(benchmark_store=store)

    def runner(backend: str, prompt: str) -> dict:
        assert backend == "ollama"
        assert prompt == "Health check"
        return {
            "response": "ok ok ok ok",
            "duration_ms": 120.0,
            "ttft_ms": 30.0,
            "token_count": 6,
        }

    monitor.register_canary_backend(
        "ollama",
        runner,
        prompt="Health check",
        interval_seconds=60,
    )

    first = monitor.run_due_canaries(now=100.0)
    second = monitor.run_due_canaries(now=120.0)
    third = monitor.run_due_canaries(now=170.0)

    summary = store.summary("ollama")

    assert len(first) == 1
    assert second == []
    assert len(third) == 1
    assert summary["canary_sample_count"] == 2
    assert summary["ttft_ms_avg"] == 30.0
    assert summary["tokens_per_second_avg"] == 50.0
    assert summary["latest_source"] == "canary"

    with sqlite3.connect(sqlite_path) as connection:
        rows = connection.execute(
            "SELECT COUNT(*), MIN(source), MAX(source) FROM benchmark_samples"
        ).fetchone()
    assert rows == (2, "canary", "canary")


def test_queue_depth_reduces_local_viability() -> None:
    store = BenchmarkStore()
    store.record_benchmark_sample(
        backend="ollama",
        duration_ms=200.0,
        token_count=40,
        ttft_ms=50.0,
        queue_depth=0,
        source="canary",
    )

    idle_score = store.local_viability("ollama", _low_pressure_hardware())

    for _ in range(4):
        store.start_request("ollama")

    busy_score = store.local_viability("ollama", _low_pressure_hardware())

    assert busy_score < idle_score


def test_downgrade_ladder_prefers_smaller_local_before_cloud() -> None:
    store = BenchmarkStore()
    store.register_backend_profile(
        "ollama",
        downgrade_backends=["gpt4all"],
        cloud_fallback="openai_standard",
    )
    store.record_benchmark_sample(
        backend="ollama",
        duration_ms=4000.0,
        token_count=20,
        ttft_ms=2000.0,
        queue_depth=2,
        source="canary",
    )
    store.record_benchmark_sample(
        backend="gpt4all",
        duration_ms=250.0,
        token_count=80,
        ttft_ms=60.0,
        queue_depth=0,
        source="canary",
    )

    decision = store.recommend_downgrade(
        "ollama",
        ["ollama", "gpt4all", "openai_standard"],
        _offload_hardware(),
        cloud_provider="openai_standard",
    )

    assert decision["action"] == "downgrade_local"
    assert decision["target_provider"] == "gpt4all"


def test_downgrade_ladder_offloads_to_cloud_when_no_local_target() -> None:
    store = BenchmarkStore()
    store.register_backend_profile(
        "ollama",
        downgrade_backends=["gpt4all"],
        cloud_fallback="openai_standard",
    )
    store.record_benchmark_sample(
        backend="ollama",
        duration_ms=5000.0,
        token_count=20,
        ttft_ms=2500.0,
        queue_depth=3,
        source="canary",
    )

    decision = store.recommend_downgrade(
        "ollama",
        ["ollama", "openai_standard"],
        _offload_hardware(),
        cloud_provider="openai_standard",
    )

    assert decision["action"] == "offload_cloud"
    assert decision["target_provider"] == "openai_standard"


def test_route_planner_uses_downgrade_recommendation() -> None:
    planner = RoutePlanner()

    plan = planner.plan(
        available_backends=["ollama", "gpt4all", "openai_standard"],
        provider_override=None,
        model_override=None,
        privacy_decision=_privacy_decision(),
        intent_decision=_intent_decision("ollama"),
        hardware_status={
            **_offload_hardware(),
            "local_viability": {"ollama": 0.12, "gpt4all": 0.71},
            "downgrade_recommendations": {
                "ollama": {
                    "action": "downgrade_local",
                    "target_provider": "gpt4all",
                    "target_model": "phi3-mini",
                }
            },
        },
        benchmark_summary={},
        local_provider="ollama",
        local_model="phi3",
        cloud_provider="openai_standard",
        cloud_model="gpt-4o-mini",
    )

    assert plan.provider == "gpt4all"
    assert plan.model == "phi3-mini"
    assert plan.audit_metadata["downgrade_action"] == "downgrade_local"
