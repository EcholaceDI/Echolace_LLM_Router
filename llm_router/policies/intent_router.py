from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..intent import IntentClassifier, IntentPrediction


@dataclass
class IntentDecision:
    label: str
    confidence: float
    candidate_labels: List[str]
    recommended_provider: str
    recommended_model: str
    source: str
    raw: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "label": self.label,
            "confidence": self.confidence,
            "candidate_labels": self.candidate_labels,
            "recommended_provider": self.recommended_provider,
            "recommended_model": self.recommended_model,
            "source": self.source,
            "raw": self.raw,
        }
        payload.setdefault("recommended_backend", self.recommended_provider)
        for key, value in self.raw.items():
            payload.setdefault(key, value)
        return payload


class IntentRouter:
    def __init__(
        self,
        classifier: IntentClassifier = None,
        schema_name: Optional[str] = None,
    ):
        self.classifier = classifier or IntentClassifier()
        self.schema_name = schema_name

    def recommend(
        self,
        prompt: str,
        top_k: int = 3,
        schema_name: Optional[str] = None,
    ) -> IntentDecision:
        active_schema = schema_name or self.schema_name
        result = self.classifier.classify(
            prompt,
            schema_name=active_schema,
            top_k=max(top_k, 5),
        )
        ordered = sorted(
            result.scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        candidate_labels = [label for label, _ in ordered[:top_k]]
        return IntentDecision(
            label=result.label,
            confidence=result.confidence,
            candidate_labels=candidate_labels,
            recommended_provider=result.route.get("provider", ""),
            recommended_model=result.route.get("model", ""),
            source=result.source,
            raw=result.to_dict(),
        )

    def record_route_outcome(
        self,
        prediction: IntentDecision,
        actual_provider: str,
        actual_model: Optional[str] = None,
        accepted: bool = True,
    ) -> Dict[str, Any]:
        raw = prediction.raw
        result = IntentPrediction(
            label=prediction.label,
            confidence=float(raw.get("confidence", prediction.confidence)),
            scores=dict(raw.get("scores", {prediction.label: prediction.confidence})),
            route={
                "provider": prediction.recommended_provider,
                "model": prediction.recommended_model,
            },
            source=prediction.source,
            schema_name=raw.get("schema_name", self.schema_name or self.classifier.default_schema),
            threshold=float(raw.get("threshold", 0.0)),
            below_threshold=bool(raw.get("below_threshold", False)),
            retrieval_hits=[],
            regret_summary=dict(raw.get("route_regret", {})),
        )
        return self.classifier.record_route_outcome(
            result,
            actual_provider=actual_provider,
            actual_model=actual_model,
            accepted=accepted,
        )
