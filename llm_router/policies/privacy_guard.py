from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..privacy import PrivacyVault
from ..security import PrivacyScanResult


@dataclass
class PrivacyPolicyProfile:
    name: str
    strict_entity_types: List[str]
    hybrid_entity_types: List[str]
    allow_rehydration_entity_types: List[str]


DEFAULT_PROFILE = PrivacyPolicyProfile(
    name="default",
    strict_entity_types=["API_KEY", "BEARER_TOKEN", "SSH_PRIVATE_KEY", "SSN", "CREDIT_CARD"],
    hybrid_entity_types=["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "LOCATION", "ACCOUNT_NUMBER", "IP_ADDRESS"],
    allow_rehydration_entity_types=["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "LOCATION", "ACCOUNT_NUMBER"],
)

HIPAA_PROFILE = PrivacyPolicyProfile(
    name="hipaa",
    strict_entity_types=DEFAULT_PROFILE.strict_entity_types + ["PERSON", "LOCATION", "EMAIL_ADDRESS", "PHONE_NUMBER"],
    hybrid_entity_types=["IP_ADDRESS"],
    allow_rehydration_entity_types=["PERSON"],
)

GDPR_PROFILE = PrivacyPolicyProfile(
    name="gdpr",
    strict_entity_types=DEFAULT_PROFILE.strict_entity_types + ["PERSON", "LOCATION", "EMAIL_ADDRESS", "PHONE_NUMBER", "IP_ADDRESS"],
    hybrid_entity_types=["ACCOUNT_NUMBER"],
    allow_rehydration_entity_types=[],
)

PCI_PROFILE = PrivacyPolicyProfile(
    name="pci",
    strict_entity_types=DEFAULT_PROFILE.strict_entity_types + ["ACCOUNT_NUMBER"],
    hybrid_entity_types=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
    allow_rehydration_entity_types=["PERSON", "EMAIL_ADDRESS"],
)

SOC2_PROFILE = PrivacyPolicyProfile(
    name="soc2",
    strict_entity_types=DEFAULT_PROFILE.strict_entity_types,
    hybrid_entity_types=DEFAULT_PROFILE.hybrid_entity_types,
    allow_rehydration_entity_types=DEFAULT_PROFILE.allow_rehydration_entity_types,
)

PROFILE_MAP = {
    "default": DEFAULT_PROFILE,
    "hipaa": HIPAA_PROFILE,
    "gdpr": GDPR_PROFILE,
    "pci": PCI_PROFILE,
    "soc2": SOC2_PROFILE,
}


@dataclass
class PrivacyDecision:
    execution_mode: str
    request_id: Optional[str]
    scan_result: PrivacyScanResult
    prompt_for_cloud: Any
    prompt_for_local: Any
    allow_rehydration: bool
    allowed_entity_types: List[str]
    profile: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "request_id": self.request_id,
            "allow_rehydration": self.allow_rehydration,
            "allowed_entity_types": self.allowed_entity_types,
            "profile": self.profile,
            "scan_result": self.scan_result.to_dict(),
        }


class PrivacyGuard:
    def __init__(self, vault: Optional[PrivacyVault] = None):
        self.vault = vault or PrivacyVault()

    def evaluate(
        self,
        prompt: Any,
        enabled: bool = False,
        profile_name: str = "default",
    ) -> PrivacyDecision:
        scan_result = self.vault.scan(prompt)
        profile = PROFILE_MAP.get(profile_name.lower(), DEFAULT_PROFILE)

        request_id = None
        execution_mode = "cloud_allowed"
        allow_rehydration = False
        allowed_entity_types: List[str] = []

        if enabled and scan_result.contains_pii:
            entity_types = set(scan_result.entity_types())
            strict_match = bool(entity_types.intersection(profile.strict_entity_types))
            hybrid_match = bool(entity_types.intersection(profile.hybrid_entity_types))
            if strict_match or scan_result.highest_risk == "regulated":
                execution_mode = "strict_local"
            elif hybrid_match or scan_result.highest_risk in ("confidential", "internal"):
                execution_mode = "hybrid_redacted"
                allow_rehydration = True
                allowed_entity_types = list(profile.allow_rehydration_entity_types)
            else:
                execution_mode = "cloud_allowed"

            record = self.vault.store_scan(scan_result)
            request_id = record["request_id"]

        return PrivacyDecision(
            execution_mode=execution_mode,
            request_id=request_id,
            scan_result=scan_result,
            prompt_for_cloud=scan_result.redacted_payload if scan_result.source_kind != "text" else scan_result.redacted_text,
            prompt_for_local=prompt,
            allow_rehydration=allow_rehydration,
            allowed_entity_types=allowed_entity_types,
            profile=profile.name,
        )

    def postprocess_response(self, response: str, decision: PrivacyDecision) -> str:
        if (
            decision.execution_mode == "hybrid_redacted"
            and decision.allow_rehydration
            and decision.request_id
        ):
            return self.vault.rehydrate(
                response,
                decision.request_id,
                allowed_entity_types=decision.allowed_entity_types,
            )
        return response
