from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

if TYPE_CHECKING:
    from .pii import PrivacyFinding


@dataclass
class RedactionResult:
    text: str
    placeholder_map: Dict[str, str]
    entity_map: Dict[str, str]


def redact_text(text: str, findings: Iterable["PrivacyFinding"]) -> RedactionResult:
    ordered = sorted(findings, key=lambda item: (item.start, item.end))
    if not ordered:
        return RedactionResult(text=text, placeholder_map={}, entity_map={})

    chunks: List[str] = []
    placeholder_map: Dict[str, str] = {}
    entity_map: Dict[str, str] = {}
    entity_counts: Dict[str, int] = {}
    cursor = 0

    for finding in ordered:
        if finding.start < cursor:
            continue
        chunks.append(text[cursor : finding.start])
        entity_counts[finding.entity_type] = (
            entity_counts.get(finding.entity_type, 0) + 1
        )
        placeholder = "<{0}_{1}>".format(
            finding.entity_type,
            entity_counts[finding.entity_type],
        )
        placeholder_map[placeholder] = finding.match
        entity_map[placeholder] = finding.entity_type
        chunks.append(placeholder)
        cursor = finding.end

    chunks.append(text[cursor:])
    return RedactionResult(
        text="".join(chunks),
        placeholder_map=placeholder_map,
        entity_map=entity_map,
    )


def rehydrate_text(
    text: str,
    placeholder_map: Dict[str, str],
    entity_map: Optional[Dict[str, str]] = None,
    allowed_entity_types: Optional[Iterable[str]] = None,
) -> str:
    allowed = set(allowed_entity_types or [])
    hydrated = text
    for placeholder, value in placeholder_map.items():
        if (
            entity_map is not None
            and allowed
            and entity_map.get(placeholder) not in allowed
        ):
            continue
        hydrated = hydrated.replace(placeholder, value)
    return hydrated
