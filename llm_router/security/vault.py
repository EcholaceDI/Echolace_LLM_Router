import importlib.util
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

from .redaction import rehydrate_text


@dataclass
class VaultRecord:
    request_id: str
    placeholder_map: Dict[str, str]
    entity_map: Dict[str, str]
    findings: List[Dict[str, Any]]
    created_at: float
    encrypted: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "placeholder_map": self.placeholder_map,
            "entity_map": self.entity_map,
            "findings": self.findings,
            "created_at": self.created_at,
            "encrypted": self.encrypted,
        }


class EphemeralVault:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._records: Dict[str, Any] = {}
        self._fernet = self._build_fernet()

    def store(
        self,
        placeholder_map: Dict[str, str],
        entity_map: Dict[str, str],
        findings: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> VaultRecord:
        record = VaultRecord(
            request_id=request_id or str(uuid.uuid4()),
            placeholder_map=placeholder_map,
            entity_map=entity_map,
            findings=findings,
            created_at=time.time(),
            encrypted=self._fernet is not None,
        )
        payload = json.dumps(record.to_dict()).encode("utf-8")
        self._records[record.request_id] = (
            self._fernet.encrypt(payload)
            if self._fernet is not None
            else record.to_dict()
        )
        self.purge_expired()
        return record

    def get(self, request_id: str) -> Optional[VaultRecord]:
        stored = self._records.get(request_id)
        if stored is None:
            return None
        if self._fernet is not None and isinstance(stored, bytes):
            payload = json.loads(self._fernet.decrypt(stored).decode("utf-8"))
        else:
            payload = cast(Dict[str, Any], stored)
        return VaultRecord(
            request_id=payload["request_id"],
            placeholder_map=dict(payload["placeholder_map"]),
            entity_map=dict(payload["entity_map"]),
            findings=list(payload["findings"]),
            created_at=float(payload["created_at"]),
            encrypted=bool(payload["encrypted"]),
        )

    def rehydrate(
        self,
        request_id: str,
        text: str,
        allowed_entity_types: Optional[List[str]] = None,
    ) -> str:
        record = self.get(request_id)
        if record is None:
            return text
        return rehydrate_text(
            text,
            record.placeholder_map,
            record.entity_map,
            allowed_entity_types=allowed_entity_types,
        )

    def purge(self, request_id: str) -> None:
        self._records.pop(request_id, None)

    def purge_expired(self) -> None:
        now = time.time()
        expired = []
        for request_id in list(self._records):
            record = self.get(request_id)
            if record is None:
                expired.append(request_id)
                continue
            if now - record.created_at > self.ttl_seconds:
                expired.append(request_id)
        for request_id in expired:
            self.purge(request_id)

    def _build_fernet(self):
        if importlib.util.find_spec("cryptography.fernet") is None:
            return None
        try:
            from cryptography.fernet import Fernet

            return Fernet(Fernet.generate_key())
        except Exception:
            return None
