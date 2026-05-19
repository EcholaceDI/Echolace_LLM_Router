# google_backend.py

import importlib.util
import os
from typing import Any, Dict, Generator, Optional

from ..base import DependencyMissingError, LLMBackend


class GoogleBackend(LLMBackend):
    """
    Google Gemini backend for Echolace DI LLM Router.
    Provides:
        - generate()  → full text response
        - stream()    → structured token stream (Format C)
    """

    name = "google"

    # ---------------------------------------------------------
    # Availability checks
    # ---------------------------------------------------------
    @classmethod
    def _has_library(cls) -> bool:
        return importlib.util.find_spec("google.generativeai") is not None

    @classmethod
    def _has_api_key(cls) -> bool:
        return os.getenv("GOOGLE_API_KEY") is not None

    @classmethod
    def available(cls) -> bool:
        return cls._has_library() and cls._has_api_key()

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {
            "api_key": "FOUND" if cls._has_api_key() else "MISSING",
            "library": "FOUND" if cls._has_library() else "MISSING",
        }

    # ---------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------
    def __init__(self, model: Optional[str] = None, **kwargs):
        # Dependency check
        if not self._has_library():
            raise DependencyMissingError(
                "google-generativeai (install via: pip install google-generativeai)"
            )

        try:
            import google.generativeai as genai
        except Exception as exc:
            raise DependencyMissingError("google-generativeai") from exc

        self.genai = genai

        # API key validation
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. "
                "Export GOOGLE_API_KEY or pass provider credentials."
            )

        self.genai.configure(api_key=api_key)

        # Model selection
        self.model_name = model or os.getenv("GOOGLE_MODEL", "gemini-1.5-pro-latest")

        # Save additional backend config
        self.kwargs = kwargs

        # Load model instance
        self.model = self.genai.GenerativeModel(self.model_name)

    # ---------------------------------------------------------
    # Full-response mode
    # ---------------------------------------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        """Assemble full output from stream()."""
        tokens = []
        for part in self.stream(prompt, **kwargs):
            tokens.append(part["token"])
        return "".join(tokens)

    # ---------------------------------------------------------
    # Streaming mode
    # ---------------------------------------------------------
    def stream(self, prompt: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Yields:
            {
                "token": <string>,
                "raw": <full raw Gemini chunk>
            }
        """

        args = {
            "max_output_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
        }
        args.update(self.kwargs)

        # Gemini streaming API
        response = self.model.generate_content(prompt, stream=True, **args)

        for chunk in response:
            token = ""

            # Typical Gemini chunk structure:
            # chunk.candidates[0].content[0].text
            try:
                cands = getattr(chunk, "candidates", None)
                if cands and cands[0].content:
                    part = cands[0].content[0]
                    token = getattr(part, "text", "") or ""
            except Exception:
                token = ""

            yield {
                "token": token,
                "raw": chunk,
            }
