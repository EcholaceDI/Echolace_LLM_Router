# gguf_backend.py

import importlib.util
import os
from typing import Any, Dict, Generator, Optional

from ..base import DependencyMissingError, LLMBackend


class GGUFBackend(LLMBackend):
    """
    GGUF backend using llama-cpp-python.
    """

    name = "gguf"

    @classmethod
    def _has_library(cls) -> bool:
        return importlib.util.find_spec("llama_cpp") is not None

    @classmethod
    def _model_path(cls) -> Optional[str]:
        return os.getenv("GGUF_MODEL_PATH")

    @classmethod
    def available(cls) -> bool:
        if not cls._has_library():
            return False
        model_path = cls._model_path()
        return model_path is not None and os.path.exists(model_path)

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        model_path = cls._model_path()
        return {
            "llama_cpp": "FOUND" if cls._has_library() else "MISSING",
            "model_path": model_path or "MISSING",
            "model_exists": os.path.exists(model_path) if model_path else False,
        }

    def __init__(self, model: Optional[str] = None, **kwargs: Any):
        if not self._has_library():
            raise DependencyMissingError(
                "llama_cpp (install via: pip install llama-cpp-python)"
            )

        try:
            from llama_cpp import Llama
        except Exception as exc:
            raise DependencyMissingError("llama-cpp-python") from exc

        model_path = model or os.getenv("GGUF_MODEL_PATH")
        if not model_path:
            raise RuntimeError(
                "GGUF backend requires a model path. Provide model='path/to/model.gguf' "
                "or set GGUF_MODEL_PATH."
            )
        if not os.path.exists(model_path):
            raise RuntimeError(f"GGUF model file not found at: {model_path}")

        super().__init__(model=model_path, **kwargs)
        self.context = int(os.getenv("GGUF_CTX", "4096"))
        self.gpu_layers = int(os.getenv("GGUF_GPU_LAYERS", "0"))
        self.llama = Llama(
            model_path=model_path,
            n_ctx=self.context,
            n_gpu_layers=self.gpu_layers,
            logits_all=False,
            vocab_only=False,
            use_mmap=True,
            use_mlock=False,
        )

    def generate(self, prompt: str, **kwargs: Any) -> str:
        tokens = []
        for part in self.stream(prompt, **kwargs):
            tokens.append(part["token"])
        return "".join(tokens)

    def stream(
        self, prompt: str, **kwargs: Any
    ) -> Generator[Dict[str, Any], None, None]:
        args = {
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.95),
            "stop": kwargs.get("stop"),
            "stream": True,
        }
        args.update(self.config)

        for raw_chunk in self.llama(prompt, **args):
            token = ""
            try:
                choices = raw_chunk.get("choices")
                if choices and len(choices) > 0:
                    token = choices[0].get("text", "")
            except Exception:
                token = ""

            yield {
                "token": token,
                "raw": raw_chunk,
            }
