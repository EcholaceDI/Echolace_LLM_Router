# lmstudio_backend.py
import json
import os
from typing import Any, Dict, Generator, Optional

import requests

from ..base import DependencyMissingError, LLMBackend


class LMStudioBackend(LLMBackend):
    """
    LM Studio Backend

    Works with LM Studio's OpenAI-compatible REST API.
    No native deps. Perfect for Windows.

    Default server URL:
        http://localhost:1234/v1

    To run LM Studio server:
        1. Open LM Studio
        2. Load a model
        3. Enable "OpenAI Compatible Server"
    """

    name = "lmstudio"

    DEFAULT_URL = "http://localhost:1234/v1"

    @classmethod
    def _base_url(cls) -> str:
        env = os.getenv("LMSTUDIO_BASE_URL")
        return env or cls.DEFAULT_URL

    @classmethod
    def available(cls) -> bool:
        """Check if LM Studio server is reachable."""
        base = cls._base_url()
        try:
            resp = requests.get(f"{base}/models", timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        base = cls._base_url()
        try:
            resp = requests.get(f"{base}/models", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                return {
                    "status": "reachable",
                    "url": base,
                    "models": models,
                }
            return {
                "status": "unreachable",
                "url": base,
                "error": f"HTTP {resp.status_code}",
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "url": base,
                "error": str(exc),
            }

    def __init__(self, model: Optional[str] = None, **kwargs):
        self.base_url = self._base_url()
        self.model = model or os.getenv("LMSTUDIO_MODEL", None)
        self.gen_kwargs = kwargs

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Send POST request to LM Studio server."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=45,
            )
            if resp.status_code != 200:
                msg = "LM Studio backend error HTTP " f"{resp.status_code}: {resp.text}"
                raise DependencyMissingError(msg)
            return resp.json()
        except Exception as exc:
            raise DependencyMissingError(f"LM Studio request failed: {exc}")

    def generate(self, prompt: str, **kwargs) -> str:
        """Non-streaming generation."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        payload.update(self.gen_kwargs)
        payload.update(kwargs)

        result = self._post("/chat/completions", payload)

        try:
            choices = result.get("choices", [{}])
            msg = choices[0].get("message", {})
            return msg.get("content", "")
        except Exception:
            return json.dumps(result)

    def stream(self, prompt: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Streaming generation."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        payload.update(self.gen_kwargs)
        payload.update(kwargs)

        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}

        with requests.post(
            url,
            headers=headers,
            json=payload,
            stream=True,
        ) as resp:
            if resp.status_code != 200:
                msg = (
                    "LM Studio streaming error HTTP " f"{resp.status_code}: {resp.text}"
                )
                raise DependencyMissingError(msg)

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    if line.startswith(b"data:"):
                        data = line[len(b"data:") :]
                        raw = json.loads(data.decode("utf-8"))
                        ch = (
                            raw.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        yield {"token": ch, "raw": raw}
                except Exception:
                    continue
