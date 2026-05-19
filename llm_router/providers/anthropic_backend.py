# anthropic_backend.py

import importlib.util
import os
from typing import Any, Dict, Generator

from ..base import DependencyMissingError, LLMBackend


class AnthropicBackend(LLMBackend):
    """
    Unified Anthropic backend.
    Supports both:
      - generate() → full text response
      - stream() → structured token streaming (Format C)

    Works with Claude 3.5, 3.7, 4.5 (Sonnet) etc.
    """

    name = "anthropic"

    @classmethod
    def _has_library(cls) -> bool:
        return importlib.util.find_spec("anthropic") is not None

    @classmethod
    def _has_api_key(cls) -> bool:
        return os.getenv("ANTHROPIC_API_KEY") is not None

    @classmethod
    def available(cls) -> bool:
        return cls._has_api_key() and cls._has_library()

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {
            "api_key": "FOUND" if cls._has_api_key() else "MISSING",
            "library": "FOUND" if cls._has_library() else "MISSING"
        }

    def __init__(self, model: str = None, **kwargs):
        # Ensure dependency installed
        if not self._has_library():
            raise DependencyMissingError("anthropic library not installed")

        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Default to Claude Sonnet 4.5 if no model specified
        # Can be overridden by setting ANTHROPIC_MODEL in the environment
        self.model = (
            model or
            os.getenv("ANTHROPIC_MODEL", "claude-4-5-sonnet-latest")
        )

        # Store additional kwargs (temp, max_tokens, etc.)
        self.kwargs = kwargs

    # -----------------------------
    # Full Response Mode
    # -----------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Return full concatenated text response.
        Internally uses the streaming API so the output matches stream().
        """
        parts = []

        for token_obj in self.stream(prompt, **kwargs):
            parts.append(token_obj["token"])

        return "".join(parts)

    # -----------------------------
    # Streaming Mode (Format C)
    # -----------------------------
    def stream(
        self,
        prompt: str,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Structured streaming output.

        Yields:
            {
                "token": <string>,
                "raw": <raw provider chunk>
            }
        """

        # Build message request
        request_payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        # Merge backend-level defaults too
        request_payload.update(self.kwargs)

        # Begin streaming
        with self.client.messages.stream(**request_payload) as stream:
            for event in stream:
                # Anthropic streaming events often look like:
                # { "type": "content_block_delta", "delta": {"text": "..."} }
                token = ""

                try:
                    if (
                        event.type == "content_block_delta" and
                        hasattr(event, "delta") and
                        hasattr(event.delta, "text") and
                        event.delta.text
                    ):
                        token = event.delta.text

                except Exception:
                    token = ""

                yield {
                    "token": token,
                    "raw": event,
                }
