# image_hf_local_backend.py

import os
import importlib.util
from typing import Any, Dict, Optional, List

from ..base import LLMBackend
from .auto_installer import install_package

class HuggingFaceImageLocalBackend(LLMBackend):
    """
    Local HuggingFace vision backend for image+text.

    Loads vision models like llava via LlavaForConditionalGeneration + LlavaProcessor.
    Env vars:
      HF_IMAGE_MODEL = "llava-hf/llava-1.5-7b-hf"  # or path
    Supports messages with image_urls (base64 or file paths).
    """

    name = "hf_image_local"

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
        model_path = os.getenv("HF_IMAGE_MODEL")
        return model_path is not None  # Existence check in init

    @classmethod
    def diagnose(cls) -> Dict[str, Any]:
        model_path = os.getenv("HF_IMAGE_MODEL")
        return {
            "transformers": "FOUND" if cls._has_transformers() else "MISSING",
            "torch": "FOUND" if cls._has_torch() else "MISSING",
            "model_path": model_path if model_path else "MISSING",
        }

    def __init__(self, model: Optional[str] = None, **kwargs):
        # Install deps if missing
        if not self._has_transformers():
            install_package("transformers")
        if not self._has_torch():
            install_package("torch")

        from transformers import LlavaForConditionalGeneration, LlavaProcessor
        import torch
        from PIL import Image  # For loading images
        import base64
        import io

        self.model_path = model or os.getenv("HF_IMAGE_MODEL")
        if not self.model_path:
            raise RuntimeError("HF_IMAGE_MODEL not set.")

        # Device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.torch = torch
        self.Processor = LlavaProcessor
        self.Model = LlavaForConditionalGeneration
        self.Image = Image
        self.base64 = base64
        self.io = io

        # Load processor and model
        self.processor = self.Processor.from_pretrained(self.model_path)
        self.model = self.Model.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map=self.device,
        )
        self.kwargs = kwargs

    def generate(self, messages: List[Dict], **kwargs) -> str:
        # Convert messages to LLaVA format (text with <image> placeholders)
        prompt = ""
        images = []
        for msg in messages:
            if msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, str):
                    prompt += content
                else:  # List of dicts
                    for item in content:
                        if item["type"] == "text":
                            prompt += item["text"]
                        elif item["type"] == "image_url":
                            url = item["image_url"]["url"]
                            if url.startswith("data:image"):
                                # Base64
                                base64_str = url.split(",")[1]
                                img_data = self.base64.b64decode(base64_str)
                                img = self.Image.open(self.io.BytesIO(img_data))
                            else:
                                # File path
                                img = self.Image.open(url)
                            images.append(img)
                            prompt += "<image>"  # LLaVA placeholder

        inputs = self.processor(prompt, images=images, return_tensors="pt").to(self.device)
        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_tokens", 256),
            "temperature": kwargs.get("temperature", 0.7),
        }
        gen_kwargs.update(self.kwargs)

        output = self.model.generate(**inputs, **gen_kwargs)
        response = self.processor.decode(output[0], skip_special_tokens=True)
        return response[len(prompt):].strip()  # Trim prompt

    # Stream can be simulated similar to hf_local, using generate with do_sample and yield tokens

# Add to REGISTERED_BACKENDS in __init__.py
