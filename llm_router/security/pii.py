import importlib.util
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .redaction import redact_text

ENTITY_RISK_LEVELS = {
    "API_KEY": "regulated",
    "BEARER_TOKEN": "regulated",
    "SSH_PRIVATE_KEY": "regulated",
    "SSN": "regulated",
    "CREDIT_CARD": "regulated",
    "PERSON": "confidential",
    "LOCATION": "confidential",
    "EMAIL_ADDRESS": "confidential",
    "PHONE_NUMBER": "confidential",
    "IP_ADDRESS": "internal",
    "ACCOUNT_NUMBER": "confidential",
    "DEFAULT": "internal",
}


@dataclass
class PrivacyFinding:
    entity_type: str
    match: str
    start: int
    end: int
    source: str
    score: float
    risk_level: str
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "match": self.match,
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "score": self.score,
            "risk_level": self.risk_level,
            "path": self.path,
        }


@dataclass
class PrivacyScanResult:
    findings: List[PrivacyFinding]
    redacted_text: str
    placeholder_map: Dict[str, str]
    entity_map: Dict[str, str]
    redacted_payload: Optional[Any] = None
    source_kind: str = "text"

    @property
    def contains_pii(self) -> bool:
        return bool(self.findings)

    @property
    def highest_risk(self) -> str:
        order = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "regulated": 3,
        }
        highest = "public"
        for finding in self.findings:
            if order[finding.risk_level] > order[highest]:
                highest = finding.risk_level
        return highest

    def entity_types(self) -> List[str]:
        seen = []
        for finding in self.findings:
            if finding.entity_type not in seen:
                seen.append(finding.entity_type)
        return seen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contains_pii": self.contains_pii,
            "highest_risk": self.highest_risk,
            "findings": [finding.to_dict() for finding in self.findings],
            "redacted_text": self.redacted_text,
            "placeholder_map": self.placeholder_map,
            "entity_map": self.entity_map,
            "entity_types": self.entity_types(),
            "redacted_payload": self.redacted_payload,
            "source_kind": self.source_kind,
        }


class PiiInspector:
    REGEX_PATTERNS = {
        "API_KEY": [
            re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        ],
        "BEARER_TOKEN": [
            re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b", re.IGNORECASE),
        ],
        "SSH_PRIVATE_KEY": [
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ],
        "SSN": [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        ],
        "EMAIL_ADDRESS": [
            re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        ],
        "PHONE_NUMBER": [
            re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
        ],
        "PERSON": [
            re.compile(r"\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}\b"),
        ],
        "LOCATION": [
            re.compile(
                r"\b\d{1,6}\s+[A-Za-z0-9.\- ]+\s(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b"
            ),
        ],
        "ACCOUNT_NUMBER": [
            re.compile(r"\b\d{8,17}\b"),
        ],
        "IP_ADDRESS": [
            re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        ],
    }

    def __init__(self, use_presidio: bool = True):
        self.use_presidio = use_presidio
        self._analyzer = None

    def scan(self, payload: Any) -> PrivacyScanResult:
        if isinstance(payload, str):
            return self.scan_text(payload)
        return self.scan_payload(payload)

    def scan_text(self, text: str) -> PrivacyScanResult:
        findings = self._regex_findings(text)
        findings.extend(self._presidio_findings(text))
        findings = self._dedupe_findings(findings)
        redaction = redact_text(text, findings)
        return PrivacyScanResult(
            findings=findings,
            redacted_text=redaction.text,
            placeholder_map=redaction.placeholder_map,
            entity_map=redaction.entity_map,
            redacted_payload=redaction.text,
            source_kind="text",
        )

    def scan_payload(self, payload: Any) -> PrivacyScanResult:
        normalized = self._normalize_payload(payload)
        findings: List[PrivacyFinding] = []
        placeholder_map: Dict[str, str] = {}
        entity_map: Dict[str, str] = {}
        redacted_payload = self._scan_value(
            normalized,
            path="$",
            findings=findings,
            placeholder_map=placeholder_map,
            entity_map=entity_map,
        )
        findings = self._dedupe_findings(findings)
        redacted_text = self.stringify_payload(redacted_payload)
        return PrivacyScanResult(
            findings=findings,
            redacted_text=redacted_text,
            placeholder_map=placeholder_map,
            entity_map=entity_map,
            redacted_payload=redacted_payload,
            source_kind=self._payload_kind(payload),
        )

    def stringify_payload(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(payload)

    def extract_text(self, payload: Any) -> str:
        fragments: List[str] = []
        self._collect_text(payload, fragments)
        return "\n".join(fragment for fragment in fragments if fragment)

    def _regex_findings(self, text: str) -> List[PrivacyFinding]:
        findings: List[PrivacyFinding] = []
        for entity_type, patterns in self.REGEX_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    findings.append(
                        PrivacyFinding(
                            entity_type=entity_type,
                            match=match.group(0),
                            start=match.start(),
                            end=match.end(),
                            source="regex",
                            score=0.85,
                            risk_level=_risk_level(entity_type),
                            path=None,
                        )
                    )
        return findings

    def _presidio_findings(self, text: str) -> List[PrivacyFinding]:
        if (
            not self.use_presidio
            or importlib.util.find_spec("presidio_analyzer") is None
        ):
            return []

        try:
            if self._analyzer is None:
                from presidio_analyzer import AnalyzerEngine

                self._analyzer = AnalyzerEngine()

            findings: List[PrivacyFinding] = []
            results = self._analyzer.analyze(text=text, language="en")
            for result in results:
                entity_type = str(result.entity_type)
                findings.append(
                    PrivacyFinding(
                        entity_type=entity_type,
                        match=text[result.start : result.end],
                        start=int(result.start),
                        end=int(result.end),
                        source="presidio",
                        score=float(result.score),
                        risk_level=_risk_level(entity_type),
                        path=None,
                    )
                )
            return findings
        except Exception:
            return []

    def _dedupe_findings(self, findings: List[PrivacyFinding]) -> List[PrivacyFinding]:
        deduped: List[PrivacyFinding] = []
        seen = set()
        for finding in sorted(
            findings, key=lambda item: (item.start, -(item.end - item.start))
        ):
            key = (
                finding.entity_type,
                finding.start,
                finding.end,
                finding.match,
                finding.path,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _scan_value(
        self,
        value: Any,
        path: str,
        findings: List[PrivacyFinding],
        placeholder_map: Dict[str, str],
        entity_map: Dict[str, str],
    ) -> Any:
        if isinstance(value, dict):
            redacted: Dict[str, Any] = {}
            for key, item in value.items():
                child_path = "{0}.{1}".format(path, key)
                redacted[key] = self._scan_value(
                    item,
                    child_path,
                    findings,
                    placeholder_map,
                    entity_map,
                )
            return redacted

        if isinstance(value, list):
            return [
                self._scan_value(
                    item,
                    "{0}[{1}]".format(path, index),
                    findings,
                    placeholder_map,
                    entity_map,
                )
                for index, item in enumerate(value)
            ]

        if value is None or isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            text = str(value)
            redacted_text = self._scan_leaf_text(
                text,
                path,
                findings,
                placeholder_map,
                entity_map,
            )
            return redacted_text if redacted_text != text else value

        text = str(value)
        return self._scan_leaf_text(
            text,
            path,
            findings,
            placeholder_map,
            entity_map,
        )

    def _scan_leaf_text(
        self,
        text: str,
        path: str,
        findings: List[PrivacyFinding],
        placeholder_map: Dict[str, str],
        entity_map: Dict[str, str],
    ) -> str:
        local_findings = self._regex_findings(text)
        local_findings.extend(self._presidio_findings(text))
        local_findings = self._dedupe_findings(local_findings)
        if not local_findings:
            return text

        for finding in local_findings:
            finding.path = path
        findings.extend(local_findings)
        redaction = redact_text(text, local_findings)
        placeholder_map.update(redaction.placeholder_map)
        entity_map.update(redaction.entity_map)
        return redaction.text

    def _collect_text(self, value: Any, fragments: List[str]) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                self._collect_text(value[key], fragments)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_text(item, fragments)
            return
        if value is None or isinstance(value, bool):
            return
        fragments.append(str(value))

    def _normalize_payload(self, payload: Any) -> Any:
        if isinstance(payload, tuple):
            return [self._normalize_payload(item) for item in payload]
        if isinstance(payload, dict):
            return {
                key: self._normalize_payload(value) for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self._normalize_payload(item) for item in payload]
        return payload

    def _payload_kind(self, payload: Any) -> str:
        if self._looks_like_message_list(payload):
            return "messages"
        if isinstance(payload, (dict, list, tuple)):
            return "structured"
        return "text"

    def _looks_like_message_list(self, payload: Any) -> bool:
        if not isinstance(payload, list) or not payload:
            return False
        return all(
            isinstance(item, dict) and ("content" in item or "role" in item)
            for item in payload
        )


def _risk_level(entity_type: str) -> str:
    return ENTITY_RISK_LEVELS.get(entity_type, ENTITY_RISK_LEVELS["DEFAULT"])
