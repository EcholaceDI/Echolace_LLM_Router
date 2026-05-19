# hf_local_backend.py

import importlib.util
import os
from typing import Any, Dict, Generator, Optional

from ..base import DependencyMissingError, LLMBackend


class HuggingFaceLocalBackend(LLMBackend):
    """
    Local HuggingFace transformers backend.

    Supports:
      - generate() → full text
      - stream()   → Format C structured streaming (simulated)

    Requires:
      - transformers
      - torch
      - HF_LOCAL_MODEL environment variable or explicit model= path
    """

    name = "hf_local"

    # ---------------------------------------------
    # Dependency checks
    # ---------------------------------------------
    @classmethod
    def _has_transformers(cls) -> bool:
        return importlib.util.find_spec("transformers") is not None

    @classmethod
    def _has_torch(cls) -> bool:
        return importlib.util.find_spec("torch") is not None

    @classmethod
    def available(cls) -> bool:
        if not cls._has_transformers() or not cls._has_torch():
            return False
        model_path = os.getenv("HF_LOCAL_MODEL")
        return model_path is not None and os.path.exists(model_path)

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        model_path = os.getenv("HF_LOCAL_MODEL")
        return {
            "transformers": "FOUND" if cls._has_transformers() else "MISSING",
            "torch": "FOUND" if cls._has_torch() else "MISSING",
            "model_path": model_path or "MISSING",
            "model_exists": os.path.exists(model_path) if model_path else False,
        }

    # ---------------------------------------------
    # Constructor
    # ---------------------------------------------
    def __init__(self, model: Optional[str] = None, **kwargs):
        # Dependency validation — no auto-install allowed
        if not self._has_transformers():
            raise DependencyMissingError(
                "transformers (install via: pip install transformers)"
            )
        if not self._has_torch():
            raise DependencyMissingError("torch (install via: pip install torch)")

        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TextIteratorStreamer,
        )

        # Determine model path
        self.model_path = model or os.getenv("HF_LOCAL_MODEL")

        if not self.model_path:
            raise RuntimeError("HF_LOCAL_MODEL not set and no model path provided.")
        if not os.path.exists(self.model_path):
            raise RuntimeError(f"Local model path does not exist: {self.model_path}")

        # Select device
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        self.torch = torch
        self.Tokenizer = AutoTokenizer
        self.Model = AutoModelForCausalLM
        self.TextIteratorStreamer = TextIteratorStreamer

        # Load tokenizer
        self.tokenizer = self.Tokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
        )

        # Load the model
        torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

        self.model = self.Model.from_pretrained(
            self.model_path,
            torch_dtype=torch_dtype,
            device_map=self.device,
            trust_remote_code=True,
        )

        self.kwargs = kwargs

    # ---------------------------------------------
    # Full text generation
    # ---------------------------------------------
    def generate(self, prompt: str, **kwargs) -> str:
        tokens = []
        for part in self.stream(prompt, **kwargs):
            tokens.append(part["token"])
        return "".join(tokens)

    # ---------------------------------------------
    # Streaming generation
    # ---------------------------------------------
    def stream(self, prompt: str, **kwargs) -> Generator[Dict[str, Any], None, None]:

        streamer = self.TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        gen_kwargs = {
            "inputs": inputs["input_ids"],
            "streamer": streamer,
            "max_new_tokens": kwargs.get("max_tokens", 256),
            "temperature": kwargs.get("temperature", 0.7),
        }

        gen_kwargs.update(self.kwargs)

        # Run generation in background thread
        import threading

        thread = threading.Thread(
            target=self.model.generate,
            kwargs=gen_kwargs,
        )
        thread.start()

        # Yield tokens as streamer emits them
        for token in streamer:
            yield {"token": token, "raw": {"text": token}}

        thread.join()


# ----------------------------------------------------------
# Fallback Heuristic Backend
# ----------------------------------------------------------
class HeuristicBackend(LLMBackend):
    """
    Simple fallback backend used when all other backends fail.
    """

    name = "heuristic"

    @classmethod
    def available(cls) -> bool:
        return True

    def diagnose(cls) -> Dict[str, Any]:
        return {"status": "fallback mode"}

    def generate(self, prompt: str, **kwargs) -> str:
        return f"(Heuristic Response) I received: {prompt}"

    def stream(self, prompt: str, **kwargs):
        for ch in f"(Heuristic Response) {prompt}":
            yield {"token": ch, "raw": None}
