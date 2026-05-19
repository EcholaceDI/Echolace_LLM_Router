# openai_universal_backend.py
import json
import os
from typing import Any, Dict, Generator, Optional

import requests

from ..base import DependencyMissingError, LLMBackend


class OpenAIUniversalBackend(LLMBackend):
    """
    Universal OpenAI-Compatible Backend

    Works with ANY HTTP endpoint that mimics OpenAI's API format:
      - DeepSeek
      - Groq
      - Together.ai
      - Fireworks.ai
      - LM Studio (OpenAI mode)
      - Cloudflare Workers AI
      - NVIDIA NIM
      - Local proxies

    Environment variables:
        UNIVERSAL_OPENAI_BASE_URL
        UNIVERSAL_OPENAI_API_KEY
        UNIVERSAL_OPENAI_MODEL

    Required:
        Base URL MUST end with `/v1`
    """

    name = "openai_universal"

    @classmethod
    def _base_url(cls) -> Optional[str]:
        return os.getenv("UNIVERSAL_OPENAI_BASE_URL")

    @classmethod
    def _api_key(cls) -> Optional[str]:
        return os.getenv("UNIVERSAL_OPENAI_API_KEY")

    @classmethod
    def available(cls) -> bool:
        """Check if the universal OpenAI-compatible endpoint is reachable."""
        base = cls._base_url()
        if not base:
            return False
        try:
            url = f"{base}/models"
            headers = {}
            api_key = cls._api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = requests.get(url, headers=headers, timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        base = cls._base_url()
        if not base:
            return {
                "status": "no_base_url",
                "error": "UNIVERSAL_OPENAI_BASE_URL not set",
            }

        headers = {}
        api_key = cls._api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            url = f"{base}/models"
            resp = requests.get(url, headers=headers, timeout=2)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
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
        base = self._base_url()
        if not base:
            raise DependencyMissingError(
                "UNIVERSAL_OPENAI_BASE_URL is not set"
            )
        self.base_url = base
        self.api_key = self._api_key()
        self.model = (
            model or
            os.getenv("UNIVERSAL_OPENAI_MODEL", "gpt-4o-mini")
        )
        self.gen_kwargs = kwargs

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            url = f"{self.base_url}{endpoint}"
            resp = requests.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=45,
            )
            if resp.status_code != 200:
                msg = (
                    "Universal OpenAI backend error HTTP "
                    f"{resp.status_code}: {resp.text}"
                )
                raise DependencyMissingError(msg)
            return resp.json()
        except Exception as exc:
            raise DependencyMissingError(
                f"Universal OpenAI request failed: {exc}"
            )

    def generate(self, prompt: str, **kwargs) -> str:
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

    def stream(
        self,
        prompt: str,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        payload.update(self.gen_kwargs)
        payload.update(kwargs)

        url = f"{self.base_url}/chat/completions"

        with requests.post(
            url,
            headers=self._headers(),
            json=payload,
            stream=True,
        ) as resp:
            if resp.status_code != 200:
                msg = (
                    "Universal OpenAI streaming error HTTP "
                    f"{resp.status_code}: {resp.text}"
                )
                raise DependencyMissingError(msg)

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    if line.startswith(b"data:"):
                        data = line[len(b"data:"):]
                        raw = json.loads(data.decode("utf-8"))
                        ch = (
                            raw.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        yield {"token": ch, "raw": raw}
                except Exception:
                    continue
