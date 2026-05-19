import hashlib
import importlib.util
import io
import math
import os
import re
from collections import defaultdict, deque
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

INTENT_LABELS = (
    "CODE",
    "DEBUGGING",
    "CREATIVE",
    "REASONING",
    "SIMPLE",
    "TRANSLATION",
    "RAG_QA",
    "TOOL_USE_OR_AGENTIC",
)


DEFAULT_INTENT_ROUTES = {
    "CODE": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
    },
    "DEBUGGING": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
    },
    "CREATIVE": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
    },
    "REASONING": {
        "provider": os.getenv("ECHOLACE_REASONING_PROVIDER", "openai_standard"),
        "model": os.getenv("ECHOLACE_REASONING_MODEL", "o1"),
    },
    "SIMPLE": {
        "provider": "ollama",
        "model": os.getenv("ECHOLACE_SIMPLE_MODEL", "phi3"),
    },
    "TRANSLATION": {
        "provider": "openai_standard",
        "model": os.getenv("ECHOLACE_TRANSLATION_MODEL", "gpt-4o-mini"),
    },
    "RAG_QA": {
        "provider": "openai_standard",
        "model": os.getenv("ECHOLACE_RAG_MODEL", "gpt-4o-mini"),
    },
    "TOOL_USE_OR_AGENTIC": {
        "provider": "openai_standard",
        "model": os.getenv("ECHOLACE_AGENTIC_MODEL", "gpt-4o-mini"),
    },
}

DEFAULT_THRESHOLDS = {
    "CODE": 0.20,
    "DEBUGGING": 0.20,
    "CREATIVE": 0.17,
    "REASONING": 0.18,
    "SIMPLE": 0.12,
    "TRANSLATION": 0.16,
    "RAG_QA": 0.16,
    "TOOL_USE_OR_AGENTIC": 0.16,
}

DEFAULT_EXEMPLARS = {
    "CODE": [
        "write python code for a data pipeline",
        "implement a feature in javascript and add unit tests",
        "refactor this function for maintainability",
        "generate a sql query for reporting",
    ],
    "DEBUGGING": [
        "debug this stack trace and explain the bug",
        "why does this test fail intermittently",
        "fix the error in this function and identify the root cause",
        "troubleshoot a failing deployment script",
    ],
    "CREATIVE": [
        "write a short story with vivid atmosphere",
        "create a brand tagline with emotional tone",
        "draft a creative campaign concept",
        "write a poem about memory and light",
    ],
    "REASONING": [
        "analyze the tradeoffs and recommend a strategy",
        "solve this complex problem step by step",
        "reason carefully about ambiguous evidence",
        "compare two architectures and defend one choice",
    ],
    "SIMPLE": [
        "summarize this note in plain language",
        "answer this basic factual question briefly",
        "give me a short explanation",
        "list the main points quickly",
    ],
    "TRANSLATION": [
        "translate this message from english to spanish",
        "rewrite this paragraph in french",
        "convert this sentence into japanese",
        "translate these support instructions into german",
    ],
    "RAG_QA": [
        "answer the question using the supplied documents",
        "ground the response in retrieved context",
        "use this knowledge base excerpt to answer",
        "cite the provided material when responding",
    ],
    "TOOL_USE_OR_AGENTIC": [
        "plan the steps and call the right tools",
        "use functions to complete this workflow",
        "coordinate actions across multiple tools",
        "build an agent plan and execute the tasks",
    ],
}


@dataclass
class IntentExample:
    label: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentSchema:
    name: str
    examples: List[IntentExample]
    routes: Dict[str, Dict[str, Any]]
    thresholds: Dict[str, float]
    fallback_label: str = "SIMPLE"


@dataclass
class RetrievalHit:
    label: str
    text: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "text": self.text,
            "score": round(self.score, 4),
        }


@dataclass
class RouteRegretRecord:
    schema_name: str
    predicted_label: str
    predicted_provider: str
    actual_provider: str
    predicted_model: Optional[str]
    actual_model: Optional[str]
    regret: float
    accepted: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "predicted_label": self.predicted_label,
            "predicted_provider": self.predicted_provider,
            "actual_provider": self.actual_provider,
            "predicted_model": self.predicted_model,
            "actual_model": self.actual_model,
            "regret": round(self.regret, 4),
            "accepted": self.accepted,
        }


@dataclass
class IntentPrediction:
    label: str
    confidence: float
    scores: Dict[str, float]
    route: Dict[str, Any]
    source: str
    schema_name: str
    threshold: float
    below_threshold: bool
    retrieval_hits: List[RetrievalHit] = field(default_factory=list)
    regret_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        ordered = sorted(
            self.scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "scores": {label: round(score, 4) for label, score in ordered},
            "candidate_labels": [label for label, _ in ordered[:3]],
            "recommended_backend": self.route.get("provider"),
            "recommended_model": self.route.get("model"),
            "source": self.source,
            "schema_name": self.schema_name,
            "threshold": round(self.threshold, 4),
            "below_threshold": self.below_threshold,
            "retrieval_hits": [hit.to_dict() for hit in self.retrieval_hits[:5]],
            "route_regret": self.regret_summary,
        }


class BaseIntentEmbedder:
    name = "base"

    def embed(self, texts: Sequence[str]) -> List[Dict[int, float]]:
        raise NotImplementedError


class HashingIntentEmbedder(BaseIntentEmbedder):
    name = "hashing"

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> List[Dict[int, float]]:
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> Dict[int, float]:
        features: Dict[int, float] = defaultdict(float)
        lowered = text.lower()
        words = re.findall(r"[a-z0-9_]+", lowered)
        for token in words:
            features[self._bucket("tok:" + token)] += 1.0
        for word in words:
            for size in (3, 4):
                if len(word) < size:
                    continue
                for index in range(len(word) - size + 1):
                    gram = word[index : index + size]
                    features[self._bucket("ng:" + gram)] += 0.35
        return _normalize_sparse(features)

    def _bucket(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % self.dimensions


class SentenceTransformerIntentEmbedder(BaseIntentEmbedder):
    name = "sentence_transformers"

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._embedder = None

    def embed(self, texts: Sequence[str]) -> List[Dict[int, float]]:
        if importlib.util.find_spec("sentence_transformers") is None:
            raise RuntimeError("sentence-transformers is not installed")

        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self._embedder = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                )

        vectors = self._embedder.encode(list(texts), normalize_embeddings=True)
        return [_normalize_dense(vector) for vector in vectors]


class IntentVectorIndex:
    def __init__(self, embedder: BaseIntentEmbedder):
        self.embedder = embedder
        self._schemas: Dict[str, List[Tuple[IntentExample, Dict[int, float]]]] = {}

    def register_schema(self, schema: IntentSchema) -> None:
        texts = [example.text for example in schema.examples]
        vectors = self.embedder.embed(texts)
        self._schemas[schema.name] = list(zip(schema.examples, vectors))

    def query(
        self,
        schema_name: str,
        text: str,
        top_k: int = 5,
    ) -> List[RetrievalHit]:
        entries = self._schemas.get(schema_name, [])
        if not entries:
            return []

        query_vector = self.embedder.embed([text])[0]
        hits: List[RetrievalHit] = []
        for example, vector in entries:
            score = _cosine_sparse(query_vector, vector)
            hits.append(
                RetrievalHit(
                    label=example.label,
                    text=example.text,
                    score=score,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]


class RouteRegretTracker:
    def __init__(self, max_records: int = 200):
        self._records: Deque[RouteRegretRecord] = deque(maxlen=max_records)

    def record(
        self,
        prediction: IntentPrediction,
        actual_provider: str,
        actual_model: Optional[str] = None,
        accepted: bool = True,
    ) -> RouteRegretRecord:
        predicted_provider = prediction.route.get("provider", "")
        predicted_model = prediction.route.get("model")
        same_provider = predicted_provider == actual_provider
        same_model = (
            predicted_model == actual_model
            if actual_model is not None
            else same_provider
        )
        regret = 0.0 if same_provider and same_model and accepted else 1.0
        record = RouteRegretRecord(
            schema_name=prediction.schema_name,
            predicted_label=prediction.label,
            predicted_provider=predicted_provider,
            actual_provider=actual_provider,
            predicted_model=predicted_model,
            actual_model=actual_model,
            regret=regret,
            accepted=accepted,
        )
        self._records.append(record)
        return record

    def summary(self) -> Dict[str, Any]:
        if not self._records:
            return {
                "count": 0,
                "mean_regret": 0.0,
            }
        regrets = [record.regret for record in self._records]
        return {
            "count": len(regrets),
            "mean_regret": round(sum(regrets) / len(regrets), 4),
            "recent": [record.to_dict() for record in list(self._records)[-5:]],
        }


class IntentClassifier:
    """
    Semantic retrieval-based intent classifier with pluggable embedders.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        enable_embeddings: Optional[bool] = None,
        embedder: Optional[BaseIntentEmbedder] = None,
        schemas: Optional[Dict[str, IntentSchema]] = None,
        default_schema: str = "default",
    ):
        self.model_name = model_name or os.getenv(
            "ECHOLACE_INTENT_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        self.enable_embeddings = (
            enable_embeddings
            if enable_embeddings is not None
            else os.getenv("ECHOLACE_ENABLE_EMBEDDINGS", "0").lower()
            in {"1", "true", "yes"}
        )
        self.embedder = embedder or self._build_default_embedder()
        self.schemas = schemas or self._build_default_schemas()
        self.default_schema = (
            default_schema if default_schema in self.schemas else "default"
        )
        self.index = IntentVectorIndex(self.embedder)
        self.route_regret_tracker = RouteRegretTracker()
        self._register_schemas()

    def classify(
        self,
        prompt: str,
        schema_name: Optional[str] = None,
        top_k: int = 5,
    ) -> IntentPrediction:
        schema = self.schemas.get(
            schema_name or self.default_schema, self.schemas[self.default_schema]
        )
        hits = self.index.query(schema.name, prompt, top_k=max(top_k, 5))
        scores = self._aggregate_scores(hits, schema)

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        label, top_score = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
        threshold = schema.thresholds.get(label, 0.15)
        below_threshold = top_score < threshold
        if below_threshold:
            label = schema.fallback_label

        confidence = self._confidence(top_score, runner_up, threshold, below_threshold)
        route = dict(
            schema.routes.get(label, DEFAULT_INTENT_ROUTES[schema.fallback_label])
        )
        return IntentPrediction(
            label=label,
            confidence=confidence,
            scores=scores,
            route=route,
            source=self.embedder.name + "_retrieval",
            schema_name=schema.name,
            threshold=threshold,
            below_threshold=below_threshold,
            retrieval_hits=hits,
            regret_summary=self.route_regret_tracker.summary(),
        )

    def register_schema(self, schema: IntentSchema) -> None:
        self.schemas[schema.name] = schema
        self.index.register_schema(schema)

    def record_route_outcome(
        self,
        prediction: IntentPrediction,
        actual_provider: str,
        actual_model: Optional[str] = None,
        accepted: bool = True,
    ) -> Dict[str, Any]:
        return self.route_regret_tracker.record(
            prediction,
            actual_provider=actual_provider,
            actual_model=actual_model,
            accepted=accepted,
        ).to_dict()

    def _register_schemas(self) -> None:
        for schema in self.schemas.values():
            self.index.register_schema(schema)

    def _build_default_embedder(self) -> BaseIntentEmbedder:
        if self.enable_embeddings:
            try:
                return SentenceTransformerIntentEmbedder(self.model_name)
            except Exception:
                pass
        return HashingIntentEmbedder()

    def _build_default_schemas(self) -> Dict[str, IntentSchema]:
        default_schema = IntentSchema(
            name="default",
            examples=[
                IntentExample(label=label, text=text)
                for label, texts in DEFAULT_EXEMPLARS.items()
                for text in texts
            ],
            routes=dict(DEFAULT_INTENT_ROUTES),
            thresholds=dict(DEFAULT_THRESHOLDS),
            fallback_label="SIMPLE",
        )
        return {"default": default_schema}

    def _aggregate_scores(
        self,
        hits: Sequence[RetrievalHit],
        schema: IntentSchema,
    ) -> Dict[str, float]:
        scores = {label: 0.0 for label in schema.routes}
        label_totals: Dict[str, List[float]] = defaultdict(list)
        for hit in hits:
            label_totals[hit.label].append(max(hit.score, 0.0))

        for label in scores:
            values = label_totals.get(label, [])
            if not values:
                continue
            scores[label] = round(sum(values[:3]) / max(len(values[:3]), 1), 6)
        return scores

    def _confidence(
        self,
        top_score: float,
        runner_up: float,
        threshold: float,
        below_threshold: bool,
    ) -> float:
        margin = max(top_score - runner_up, 0.0)
        threshold_bonus = max(top_score - threshold, 0.0)
        confidence = 0.45 + (margin * 1.5) + threshold_bonus
        if below_threshold:
            confidence *= 0.75
        return max(0.05, min(0.99, confidence))


def build_intent_schema(
    name: str,
    examples: Dict[str, Iterable[str]],
    routes: Optional[Dict[str, Dict[str, Any]]] = None,
    thresholds: Optional[Dict[str, float]] = None,
    fallback_label: str = "SIMPLE",
) -> IntentSchema:
    schema_examples = [
        IntentExample(label=label, text=text)
        for label, texts in examples.items()
        for text in texts
    ]
    schema_routes = dict(DEFAULT_INTENT_ROUTES)
    if routes:
        schema_routes.update(routes)
    schema_thresholds = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        schema_thresholds.update(thresholds)
    return IntentSchema(
        name=name,
        examples=schema_examples,
        routes=schema_routes,
        thresholds=schema_thresholds,
        fallback_label=fallback_label,
    )


def _normalize_sparse(values: Dict[int, float]) -> Dict[int, float]:
    norm = math.sqrt(sum(value * value for value in values.values()))
    if norm == 0.0:
        return dict(values)
    return {index: value / norm for index, value in values.items()}


def _normalize_dense(values: Sequence[float]) -> Dict[int, float]:
    norm = math.sqrt(sum(float(value) * float(value) for value in values))
    if norm == 0.0:
        return {}
    return {
        index: float(value) / norm
        for index, value in enumerate(values)
        if float(value) != 0.0
    }


def _cosine_sparse(left: Dict[int, float], right: Dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    total = 0.0
    for index, value in left.items():
        total += value * right.get(index, 0.0)
    return total


__all__ = [
    "BaseIntentEmbedder",
    "HashingIntentEmbedder",
    "INTENT_LABELS",
    "IntentClassifier",
    "IntentExample",
    "IntentPrediction",
    "IntentSchema",
    "IntentVectorIndex",
    "RetrievalHit",
    "RouteRegretRecord",
    "RouteRegretTracker",
    "SentenceTransformerIntentEmbedder",
    "build_intent_schema",
]
