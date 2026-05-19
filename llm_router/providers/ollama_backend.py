# ollama_backend.py
import json
import os
from typing import Any, Dict, Generator, Optional

import requests

from ..base import DependencyMissingError, LLMBackend


class OllamaBackend(LLMBackend):
    """
    Ollama Backend

    Works with the local Ollama server.

    Default server URL:
        http://localhost:11434

    Supports:
        - /api/generate   (stream + non-stream)
        - /api/tags       (model listing)
    """

    name = "ollama"

    DEFAULT_URL = "http://localhost:11434"

    @classmethod
    def _base_url(cls) -> str:
        env = os.getenv("OLLAMA_BASE_URL")
        return env or cls.DEFAULT_URL

    @classmethod
    def available(cls) -> bool:
        """Check if Ollama is running."""
        base = cls._base_url()
        try:
            url = f"{base}/api/tags"
            resp = requests.get(url, timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        base = cls._base_url()
        url = f"{base}/api/tags"
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
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
        self.model = model or os.getenv("OLLAMA_MODEL", None)
        self.gen_kwargs = kwargs

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Send POST request and return JSON."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=60,
            )
            if resp.status_code != 200:
                msg = "Ollama backend error HTTP " f"{resp.status_code}: {resp.text}"
                raise DependencyMissingError(msg)
            return resp.json()
        except Exception as exc:
            raise DependencyMissingError(f"Ollama request failed: {exc}")

    def generate(self, prompt: str, **kwargs) -> str:
        """Non-streaming text generation."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        payload.update(self.gen_kwargs)
        payload.update(kwargs)

        result = self._post("/api/generate", payload)

        try:
            return result.get("response", "")
        except Exception:
            return json.dumps(result)

    def stream(self, prompt: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Streaming output from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        payload.update(self.gen_kwargs)
        payload.update(kwargs)

        url = f"{self.base_url}/api/generate"

        with requests.post(
            url,
            json=payload,
            stream=True,
        ) as resp:
            if resp.status_code != 200:
                msg = "Ollama streaming error HTTP " f"{resp.status_code}: {resp.text}"
                raise DependencyMissingError(msg)

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    raw = json.loads(line.decode("utf-8"))
                    token = raw.get("response", "")
                    yield {"token": token, "raw": raw}
                    if raw.get("done", False):
                        break
                except Exception:
                    continue
