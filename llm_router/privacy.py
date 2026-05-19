from typing import Any, Dict, List, Optional

from .security import EphemeralVault, PiiInspector, PrivacyFinding, PrivacyScanResult


class PrivacyVault:
    """
    Backward-compatible facade over the security package.
    """

    def __init__(self, use_presidio: bool = True, ttl_seconds: int = 3600):
        self.inspector = PiiInspector(use_presidio=use_presidio)
        self.vault = EphemeralVault(ttl_seconds=ttl_seconds)

    def scan(self, payload: Any) -> PrivacyScanResult:
        return self.inspector.scan(payload)

    def store_scan(
        self,
        scan_result: PrivacyScanResult,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = self.vault.store(
            placeholder_map=scan_result.placeholder_map,
            entity_map=scan_result.entity_map,
            findings=[finding.to_dict() for finding in scan_result.findings],
            request_id=request_id,
        )
        return record.to_dict()

    def rehydrate(
        self,
        text: str,
        request_id: str,
        allowed_entity_types: Optional[List[str]] = None,
    ) -> str:
        return self.vault.rehydrate(
            request_id=request_id,
            text=text,
            allowed_entity_types=allowed_entity_types,
        )


__all__ = [
    "PrivacyFinding",
    "PrivacyScanResult",
    "PrivacyVault",
]
