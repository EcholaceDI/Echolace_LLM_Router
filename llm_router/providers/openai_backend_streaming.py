# openai_backend_streaming.py

import importlib.util
import os
from typing import Any, Dict, Generator, Optional

from ..base import DependencyMissingError, LLMBackend


class OpenAIStreamingBackend(LLMBackend):
    """
    Streaming backend for OpenAI models.

    Provides structured streaming output:
    {
        "token": <str>,
        "raw": <provider_chunk>
    }
    """

    name = "openai_streaming"

    # ---------------------------------------------
    # Availability checks
    # ---------------------------------------------
    @classmethod
    def _has_openai_lib(cls) -> bool:
        return importlib.util.find_spec("openai") is not None

    @classmethod
    def _has_api_key(cls) -> bool:
        return os.getenv("OPENAI_API_KEY") is not None

    @classmethod
    def available(cls) -> bool:
        return cls._has_openai_lib() and cls._has_api_key()

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {
            "api_key": "FOUND" if cls._has_api_key() else "MISSING",
            "openai_library": "FOUND" if cls._has_openai_lib() else "MISSING",
        }

    # ---------------------------------------------
    # Constructor
    # ---------------------------------------------
    def __init__(self, model: Optional[str] = None, **kwargs):
        if not self._has_openai_lib():
            raise DependencyMissingError("openai (install via: pip install openai)")

        if not self._has_api_key():
            raise RuntimeError(
                "OPENAI_API_KEY not set. " "Export it or pass provider credentials."
            )

        from openai import OpenAI

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # backend-level overrides
        self.kwargs = kwargs

    # ---------------------------------------------
    # Fallback generate() built from tokens
    # ---------------------------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        tokens = []
        for part in self.stream(prompt, **kwargs):
            tokens.append(part["token"])
        return "".join(tokens)

    # ---------------------------------------------
    # Streaming API
    # ---------------------------------------------
    def stream(self, prompt: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming generator yielding Format C chunks.
        """

        args = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        args.update(self.kwargs)

        # unified chat completion streaming
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **args,
        )

        for chunk in stream:
            token = ""

            # -----------------------------------------
            # Handle every OpenAI SDK version safely
            # -----------------------------------------
            try:
                # handle dict SDK responses
                if isinstance(chunk, dict):
                    choices = chunk.get("choices", [])
                else:
                    choices = getattr(chunk, "choices", [])

                if choices:
                    first = choices[0]

                    # extract delta for dict or object versions
                    if isinstance(first, dict):
                        delta = first.get("delta") or {}
                    else:
                        delta = getattr(first, "delta", {}) or {}

                    # extract content
                    if isinstance(delta, dict):
                        token = delta.get("content", "") or ""
                    else:
                        token = getattr(delta, "content", "") or ""

            except Exception:
                # Never crash the router — just emit safe empty token
                token = ""

            yield {
                "token": token,
                "raw": chunk,
            }
