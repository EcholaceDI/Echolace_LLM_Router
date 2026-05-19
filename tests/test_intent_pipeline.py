from typing import Dict, Sequence

from llm_router.intent import BaseIntentEmbedder, IntentClassifier, build_intent_schema
from llm_router.policies.engine import RequestPolicyEngine
from llm_router.policies.intent_router import IntentRouter
from llm_router.router import LLMInterface
from llm_router.telemetry.benchmark_store import BenchmarkStore


class FakeEmbedder(BaseIntentEmbedder):
    name = "fake"

    def __init__(self, mapping: Dict[str, Dict[int, float]]):
        self.mapping = mapping

    def embed(self, texts: Sequence[str]):
        return [self.mapping.get(text, {}) for text in texts]


class FakeHardwareMonitor:
    def sample(self):
        return self.current()

    def current(self):
        return {
            "cpu": {"utilization_percent": 10.0},
            "memory": {"utilization_percent": 10.0},
            "gpu": {"utilization_percent": 0.0},
            "thermal_throttling": False,
            "should_offload": False,
        }

    def local_viability(self, backend: str, privacy_priority: float = 0.0) -> float:
        return 0.9


def test_semantic_retrieval_prefers_debugging_intent() -> None:
    schema = build_intent_schema(
        "default",
        {
            "DEBUGGING": ["debug stack trace root cause", "fix failing test"],
            "TRANSLATION": ["translate this message to french"],
            "SIMPLE": ["summarize this note"],
        },
    )
    embedder = FakeEmbedder(
        {
            "debug stack trace root cause": {0: 1.0},
            "fix failing test": {0: 0.9, 1: 0.1},
            "translate this message to french": {1: 1.0},
            "summarize this note": {2: 1.0},
            "help me debug this traceback and find the bug": {0: 0.95, 1: 0.05},
        }
    )
    classifier = IntentClassifier(embedder=embedder, schemas={"default": schema})

    prediction = classifier.classify("help me debug this traceback and find the bug")

    assert prediction.label == "DEBUGGING"
    assert prediction.source == "fake_retrieval"
    assert prediction.retrieval_hits[0].label == "DEBUGGING"


def test_expanded_taxonomy_supports_translation_rag_and_agentic() -> None:
    schema = build_intent_schema(
        "default",
        {
            "TRANSLATION": ["translate this email to spanish"],
            "RAG_QA": ["answer using the provided documents"],
            "TOOL_USE_OR_AGENTIC": ["use tools to complete this workflow"],
            "SIMPLE": ["summarize briefly"],
        },
    )
    embedder = FakeEmbedder(
        {
            "translate this email to spanish": {0: 1.0},
            "answer using the provided documents": {1: 1.0},
            "use tools to complete this workflow": {2: 1.0},
            "summarize briefly": {3: 1.0},
            "please translate this customer reply into spanish": {0: 0.95},
            "use the retrieved context to answer the question": {1: 0.95},
            "plan the steps and call the correct tools": {2: 0.95},
        }
    )
    classifier = IntentClassifier(embedder=embedder, schemas={"default": schema})

    assert (
        classifier.classify("please translate this customer reply into spanish").label
        == "TRANSLATION"
    )
    assert (
        classifier.classify("use the retrieved context to answer the question").label
        == "RAG_QA"
    )
    assert (
        classifier.classify("plan the steps and call the correct tools").label
        == "TOOL_USE_OR_AGENTIC"
    )


def test_calibrated_threshold_falls_back_when_similarity_is_too_low() -> None:
    schema = build_intent_schema(
        "default",
        {
            "CODE": ["write python code"],
            "SIMPLE": ["summarize this"],
        },
        thresholds={"CODE": 0.4, "SIMPLE": 0.1},
        fallback_label="SIMPLE",
    )
    embedder = FakeEmbedder(
        {
            "write python code": {0: 1.0},
            "summarize this": {1: 1.0},
            "completely unrelated request": {7: 1.0},
        }
    )
    classifier = IntentClassifier(embedder=embedder, schemas={"default": schema})

    prediction = classifier.classify("completely unrelated request")

    assert prediction.label == "SIMPLE"
    assert prediction.below_threshold is True


def test_tenant_specific_schema_changes_intent_route() -> None:
    default_schema = build_intent_schema(
        "default",
        {
            "TOOL_USE_OR_AGENTIC": ["use tools to complete this workflow"],
            "SIMPLE": ["summarize this note"],
        },
    )
    tenant_schema = build_intent_schema(
        "tenant_acme",
        {
            "TOOL_USE_OR_AGENTIC": ["use tools to complete this workflow"],
            "RAG_QA": ["answer from the private knowledge base"],
            "SIMPLE": ["summarize this note"],
        },
        routes={
            "TOOL_USE_OR_AGENTIC": {
                "provider": "openai_standard",
                "model": "gpt-4o-mini",
            },
            "RAG_QA": {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-latest",
            },
        },
    )
    embedder = FakeEmbedder(
        {
            "use tools to complete this workflow": {0: 1.0},
            "answer from the private knowledge base": {1: 1.0},
            "summarize this note": {2: 1.0},
            "answer this from our private knowledge base": {1: 0.95},
        }
    )
    classifier = IntentClassifier(
        embedder=embedder,
        schemas={
            "default": default_schema,
            "tenant_acme": tenant_schema,
        },
        default_schema="default",
    )

    prediction = classifier.classify(
        "answer this from our private knowledge base",
        schema_name="tenant_acme",
    )

    assert prediction.label == "RAG_QA"
    assert prediction.schema_name == "tenant_acme"
    assert prediction.route["provider"] == "anthropic"


def test_route_regret_tracking_records_outcomes() -> None:
    schema = build_intent_schema(
        "default",
        {
            "DEBUGGING": ["debug the failing unit test"],
            "SIMPLE": ["summarize this"],
        },
    )
    embedder = FakeEmbedder(
        {
            "debug the failing unit test": {0: 1.0},
            "summarize this": {1: 1.0},
            "find the bug in this test failure": {0: 0.9},
        }
    )
    classifier = IntentClassifier(embedder=embedder, schemas={"default": schema})
    prediction = classifier.classify("find the bug in this test failure")

    record = classifier.record_route_outcome(
        prediction,
        actual_provider="openai_standard",
        actual_model="gpt-4o-mini",
        accepted=False,
    )

    assert record["regret"] == 1.0
    assert classifier.route_regret_tracker.summary()["count"] == 1


def test_llm_intent_uses_configurable_semantic_router() -> None:
    schema = build_intent_schema(
        "tenant_ops",
        {
            "TOOL_USE_OR_AGENTIC": ["coordinate tools across systems"],
            "SIMPLE": ["give a short answer"],
        },
    )
    embedder = FakeEmbedder(
        {
            "coordinate tools across systems": {0: 1.0},
            "give a short answer": {1: 1.0},
            "coordinate actions across systems and tools": {0: 0.97},
        }
    )
    classifier = IntentClassifier(
        embedder=embedder,
        schemas={"tenant_ops": schema, "default": schema},
        default_schema="tenant_ops",
    )
    engine = RequestPolicyEngine(
        intent_router=IntentRouter(classifier=classifier, schema_name="tenant_ops"),
        benchmark_store=BenchmarkStore(),
        hardware_monitor=FakeHardwareMonitor(),
        intent_routing=True,
        intent_schema="tenant_ops",
    )
    llm = LLMInterface(
        provider="anthropic", policy_engine=engine, intent_schema="tenant_ops"
    )

    result = llm.intent("coordinate actions across systems and tools", top_k=2)

    assert result["label"] == "TOOL_USE_OR_AGENTIC"
    assert result["schema_name"] == "tenant_ops"
    assert result["source"] == "fake_retrieval"
