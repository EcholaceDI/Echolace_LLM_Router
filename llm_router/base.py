# base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMBackendError(Exception):
    """Generic backend error for LLM routing."""

    pass


class DependencyMissingError(LLMBackendError):
    """Raised when a required Python package is missing."""

    def __init__(self, package: str):
        super().__init__(f"Missing dependency: {package}")
        self.package = package


class LLMBackend(ABC):
    """
    Abstract base class for any LLM backend.

    Every backend must implement:
      - available() → bool
      - diagnose() → dict
      - generate(prompt, **kwargs) → str

    Streaming is optional but encouraged.
    """

    # Each backend MUST override this
    name: str = "base"

    def __init__(self, model: Optional[str] = None, **kwargs):
        """
        Standardized initializer for backend interfaces.

        model: Optional default model name for this backend.
        kwargs: Additional backend-specific parameters.
        """
        self.model = model
        self.config = kwargs

    # ---------------------------------------------------------
    # Required Class Methods
    # ---------------------------------------------------------
    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """Return True if backend can be used (keys, packages, binaries)."""
        raise NotImplementedError

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        """
        Optional: Backends may override this.
        Default: backend is unavailable but reason unknown.
        """
        return {
            "name": cls.name,
            "available": cls.available(),
            "reason": "diagnostics not implemented",
        }

    # ---------------------------------------------------------
    # Required instance methods
    # ---------------------------------------------------------
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Synchronous text generation."""
        raise NotImplementedError

    # ---------------------------------------------------------
    # Optional streaming
    # ---------------------------------------------------------
    def stream(self, prompt: str, **kwargs):
        """
        Optional streaming API.
        Backends that implement streaming should override this method.
        """
        raise NotImplementedError("Streaming not supported for this backend.")
