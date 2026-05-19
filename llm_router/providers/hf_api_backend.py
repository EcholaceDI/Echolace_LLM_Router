# hf_api_backend.py

import importlib.util
import os
from typing import Any, Dict, Generator, Optional

from ..base import DependencyMissingError, LLMBackend


class HuggingFaceAPIBackend(LLMBackend):
    """
    HuggingFace Inference API backend (TGI or hosted models).

    Supports:
      - generate() → full text response
      - stream()   → structured streaming (Format C)
    """

    name = "hf_api"

    @classmethod
    def _has_library(cls) -> bool:
        return importlib.util.find_spec("huggingface_hub") is not None

    @classmethod
    def _has_api_key(cls) -> bool:
        return os.getenv("HUGGINGFACE_API_KEY") is not None

    @classmethod
    def available(cls) -> bool:
        return cls._has_api_key() and cls._has_library()

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {
            "api_key": "FOUND" if cls._has_api_key() else "MISSING",
            "library": "FOUND" if cls._has_library() else "MISSING",
        }

    def __init__(self, model: Optional[str] = None, **kwargs):
        # Dependency check
        if not self._has_library():
            raise DependencyMissingError(
                "huggingface_hub (install via: pip install huggingface_hub)"
            )

        from huggingface_hub import InferenceClient

        token = os.getenv("HUGGINGFACE_API_KEY")

        self.model_name = (
            model
            or os.getenv("HF_API_MODEL")
            or "mistralai/Mistral-7B-Instruct-v0.2"
        )

        self.client = InferenceClient(
            model=self.model_name,
            token=token,
        )

        self.kwargs = kwargs

    # ---------------------------------------------------------
    # Full Response
    # ---------------------------------------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        """Assemble full response by streaming if possible."""
        try:
            tokens = []
            for part in self.stream(prompt, **kwargs):
                tokens.append(part["token"])
            return "".join(tokens)
        except Exception:
            # Fallback non-stream mode
            response = self.client.text_generation(
                prompt,
                max_new_tokens=kwargs.get("max_tokens", 512),
                temperature=kwargs.get("temperature", 0.7),
            )
            return getattr(response, "generated_text", str(response))

    # ---------------------------------------------------------
    # Streaming Mode
    # ---------------------------------------------------------
    def stream(
        self,
        prompt: str,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:

        args = {
            "max_new_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True,
        }

        args.update(self.kwargs)

        try:
            stream = self.client.text_generation(prompt, **args)

            for chunk in stream:
                raw = chunk
                token = ""

                try:
                    if isinstance(chunk, dict):
                        if "token" in chunk and chunk["token"]:
                            token = chunk["token"].get("text", "")
                        elif "generated_text" in chunk:
                            token = chunk["generated_text"]
                        elif "text" in chunk:
                            token = chunk["text"]
                except Exception:
                    token = ""

                yield {"token": token, "raw": raw}

        except Exception as exc:
            raise RuntimeError(
                f"The HuggingFace model '{self.model_name}' does not "
                "support streaming or returned an invalid stream."
            ) from exc
