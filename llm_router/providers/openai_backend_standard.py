# openai_backend_standard.py

import importlib.util
import os
from typing import Any, Dict, Optional

from ..base import DependencyMissingError, LLMBackend


class OpenAIBackend(LLMBackend):
    """
    Standard (non-streaming) OpenAI backend.

    Supports:
      - OpenAI API (api.openai.com)
      - Azure OpenAI (AZURE_OPENAI_* environment variables)

    This backend does NOT stream. For streaming support, use OpenAIStreamingBackend.
    """

    name = "openai_standard"

    # ---------------------------------------------
    # Dependency Checks
    # ---------------------------------------------
    @classmethod
    def _has_openai_lib(cls) -> bool:
        return importlib.util.find_spec("openai") is not None

    @classmethod
    def _has_openai_key(cls) -> bool:
        return os.getenv("OPENAI_API_KEY") is not None

    @classmethod
    def _has_azure_key(cls) -> bool:
        return os.getenv("AZURE_OPENAI_API_KEY") is not None

    @classmethod
    def _requires_azure_config(cls) -> bool:
        # Azure requires three environment variables
        return (
            os.getenv("AZURE_OPENAI_ENDPOINT")
            and os.getenv("AZURE_OPENAI_API_KEY")
            and os.getenv("AZURE_OPENAI_DEPLOYMENT")
        )

    @classmethod
    def available(cls) -> bool:
        if not cls._has_openai_lib():
            return False
        return cls._has_openai_key() or cls._requires_azure_config()

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        return {
            "openai_library": "FOUND" if cls._has_openai_lib() else "MISSING",
            "openai_api_key": "FOUND" if cls._has_openai_key() else "MISSING",
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT") or "MISSING",
            "azure_api_key": "FOUND" if cls._has_azure_key() else "MISSING",
            "azure_deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT") or "MISSING",
        }

    # ---------------------------------------------
    # Constructor
    # ---------------------------------------------
    def __init__(self, model: Optional[str] = None, **kwargs):
        if not self._has_openai_lib():
            raise DependencyMissingError("openai (install via: pip install openai)")

        from openai import OpenAI

        self.kwargs = kwargs

        # ---------------------------------------------
        # OpenAI (normal)
        # ---------------------------------------------
        if self._has_openai_key():
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.is_azure = False
            return

        # ---------------------------------------------
        # Azure OpenAI
        # ---------------------------------------------
        if self._requires_azure_config():
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            key = os.getenv("AZURE_OPENAI_API_KEY")
            deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

            self.client = OpenAI(
                api_key=key, base_url=f"{endpoint}/openai/deployments/{deployment}"
            )

            # Azure deployments require a model name but ignore it internally
            self.model = model or os.getenv("OPENAI_MODEL") or "azure-model"
            self.is_azure = True
            return

        # ---------------------------------------------
        # If we reach here, nothing is configured
        # ---------------------------------------------
        raise RuntimeError(
            "Neither OPENAI_API_KEY nor Azure OpenAI credentials are set."
        )

    # ---------------------------------------------
    # Text Completion API
    # ---------------------------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Full-text response from OpenAI / Azure OpenAI.
        """

        args = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        args.update(self.kwargs)

        # Unified ChatCompletion call for OpenAI & Azure
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **args,
        )

        # Safety across SDK versions:
        try:
            return completion.choices[0].message.content
        except Exception:
            return str(completion)
