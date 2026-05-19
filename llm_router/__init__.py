# __init__.py
# flake8: noqa

"""
LLM Router Package
==================

This package provides a unified interface for many LLM backends,
including:

- OpenAI Standard
- OpenAI Streaming
- OpenAI Universal-Compatible
- Anthropic
- Google Gemini
- HuggingFace API
- HF Local (Transformers)
- GGUF (llama.cpp)
- GPT4All
- LM Studio
- Ollama

The router dynamically selects the best available backend unless
explicitly overridden.

Each backend is isolated to allow modular packaging and selling.
"""

from typing import List, Type

from .base import LLMBackend

# This list is filled dynamically via _try_import_backend().
REGISTERED_BACKENDS: List[Type[LLMBackend]] = []


def _try_import_backend(module_name: str, class_name: str) -> None:
    try:
        import importlib

        module = importlib.import_module(f".{module_name}", package="llm_router")
        backend_class = getattr(module, class_name)
        REGISTERED_BACKENDS.append(backend_class)
    except Exception:
        pass


# -------------------------------------
# Backend discovery (alphabetical order)
# -------------------------------------

# Anthropic
_try_import_backend("providers.anthropic_backend", "AnthropicBackend")

# GGUF via llama.cpp
_try_import_backend("providers.gguf_backend", "GGUFBackend")

# Google Gemini
_try_import_backend("providers.google_backend", "GoogleBackend")

# GPT4All
_try_import_backend("providers.gpt4all_backend", "GPT4AllBackend")

# HuggingFace (cloud API)
_try_import_backend("providers.hf_api_backend", "HuggingFaceAPIBackend")

# HuggingFace Local (Transformers)
_try_import_backend("providers.hf_local_backend", "HuggingFaceLocalBackend")

# LM Studio
_try_import_backend("providers.lmstudio_backend", "LMStudioBackend")

# Ollama
_try_import_backend("providers.ollama_backend", "OllamaBackend")

# OpenAI Standard
_try_import_backend("providers.openai_backend_standard", "OpenAIBackend")

# OpenAI Streaming
_try_import_backend("providers.openai_backend_streaming", "OpenAIStreamingBackend")

# Universal OpenAI-compatible (e.g., vLLM, xAI, Groq, etc.)
_try_import_backend("providers.openai_universal_backend", "OpenAIUniversalBackend")


# ----------------------
# Public Interface
# ----------------------
from .router import LLMInterface

__all__ = [
    "LLMInterface",
    "LLMBackend",
    "REGISTERED_BACKENDS",
]
