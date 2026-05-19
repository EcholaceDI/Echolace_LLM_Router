# gpt4all_backend.py
import json
import os
from typing import Any, Dict, Generator, Optional

import requests

from ..base import DependencyMissingError, LLMBackend


class GPT4AllBackend(LLMBackend):
    """
    GPT4All Backend

    Uses the GPT4All local inference server (REST API).
    This avoids llama-cpp-python entirely and works cleanly on Windows.

    Expected server command:
        gpt4all --server --model <model.gguf>

    Default endpoint:
        http://localhost:4891/v1
    """

    name = "gpt4all"

    DEFAULT_URL = "http://localhost:4891/v1"

    @classmethod
    def available(cls) -> bool:
        """Check if GPT4All server is running and reachable."""
        url = os.getenv("GPT4ALL_BASE_URL", cls.DEFAULT_URL)
        try:
            resp = requests.get(f"{url}/models", timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        """Return diagnostics for GPT4All availability."""
        url = os.getenv("GPT4ALL_BASE_URL", cls.DEFAULT_URL)
        try:
            resp = requests.get(f"{url}/models", timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                return {
                    "status": "reachable",
                    "url": url,
                    "models": models,
                }
            return {
                "status": "unreachable",
                "url": url,
                "error": f"HTTP {resp.status_code}",
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "url": url,
                "error": str(exc),
            }

    def __init__(self, model: Optional[str] = None, **kwargs):
        self.base_url = os.getenv("GPT4ALL_BASE_URL", self.DEFAULT_URL)
        self.model = model or os.getenv("GPT4ALL_MODEL", None)
        self.generate_kwargs = kwargs

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Internal helper for POST requests."""
        try:
            url = f"{self.base_url}{endpoint}"
            resp = requests.post(url, json=payload, timeout=45)
            if resp.status_code != 200:
                msg = (
                    f"GPT4All server returned HTTP {resp.status_code}: "
                    f"{resp.text}"
                )
                raise DependencyMissingError(msg)
            return resp.json()
        except Exception as exc:
            raise DependencyMissingError(
                f"GPT4All request failed: {exc}"
            )

    def generate(self, prompt: str, **kwargs) -> str:
        """Non-streaming generation."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        payload.update(self.generate_kwargs)
        payload.update(kwargs)

        result = self._post("/chat/completions", payload)

        try:
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            return message.get("content", "")
        except Exception:
            return json.dumps(result)

    def stream(
        self,
        prompt: str,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """Streaming generation."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        payload.update(self.generate_kwargs)
        payload.update(kwargs)

        url = f"{self.base_url}/chat/completions"

        with requests.post(url, json=payload, stream=True) as resp:
            if resp.status_code != 200:
                msg = (
                    "GPT4All server streaming error HTTP "
                    f"{resp.status_code}: {resp.text}"
                )
                raise DependencyMissingError(msg)

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    if line.startswith(b"data:"):
                        json_part = line[len(b"data:"):]
                        raw = json.loads(json_part.decode("utf-8"))
                        choices = raw.get("choices", [{}])
                        delta = choices[0].get("delta", {})
                        token = delta.get("content", "")
                        yield {"token": token, "raw": raw}
                except Exception:
                    continue
