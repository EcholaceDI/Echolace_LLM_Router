from llm_router.policies.privacy_guard import PrivacyGuard
from llm_router.privacy import PrivacyVault
from llm_router.security import PiiInspector


def test_json_payload_pii_detection_redacts_nested_fields() -> None:
    inspector = PiiInspector(use_presidio=False)
    payload = {
        "customer": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "account": {"ssn": "123-45-6789"},
        },
        "notes": [
            "safe",
            {"contact": {"phone": "555-123-4567"}},
        ],
    }

    result = inspector.scan(payload)

    assert result.contains_pii is True
    assert result.source_kind == "structured"
    assert result.redacted_payload["customer"]["email"] == "<EMAIL_ADDRESS_1>"
    assert result.redacted_payload["customer"]["account"]["ssn"] == "<SSN_1>"
    assert result.redacted_payload["notes"][1]["contact"]["phone"] == "<PHONE_NUMBER_1>"
    assert "$.customer.email" in [finding.path for finding in result.findings]
    assert "$.customer.account.ssn" in [finding.path for finding in result.findings]


def test_message_list_payload_detection_redacts_before_cloud_routing() -> None:
    guard = PrivacyGuard(vault=PrivacyVault(use_presidio=False))
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "My email is bob@example.com"},
    ]

    decision = guard.evaluate(messages, enabled=True, profile_name="default")

    assert decision.scan_result.source_kind == "messages"
    assert decision.execution_mode == "hybrid_redacted"
    assert decision.prompt_for_cloud[1]["content"] == "My email is <EMAIL_ADDRESS_1>"
    assert decision.prompt_for_local == messages


def test_strict_local_blocks_sensitive_structured_payload_without_local_backend() -> None:
    guard = PrivacyGuard(vault=PrivacyVault(use_presidio=False))
    payload = {"patient": {"name": "Jane Doe", "ssn": "123-45-6789"}}

    decision = guard.evaluate(payload, enabled=True, profile_name="hipaa")

    assert decision.execution_mode == "strict_local"
    assert decision.scan_result.highest_risk == "regulated"
    assert decision.request_id is not None


def test_hybrid_redacted_response_is_rehydrated_when_allowed() -> None:
    guard = PrivacyGuard(vault=PrivacyVault(use_presidio=False))
    payload = {"contact": {"email": "jane@example.com"}}

    decision = guard.evaluate(payload, enabled=True, profile_name="default")
    response = guard.postprocess_response(
        "Send a note to <EMAIL_ADDRESS_1> today.",
        decision,
    )

    assert decision.execution_mode == "hybrid_redacted"
    assert response == "Send a note to jane@example.com today."
