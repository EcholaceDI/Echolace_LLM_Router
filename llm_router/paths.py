"""
Project-relative path helpers for the Echolace LLM Router.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    """Return the project root (Echolace_LLM_Router) directory."""
    return _REPO_ROOT


def _path_from_env(env_var: str) -> Optional[Path]:
    raw = os.getenv(env_var)
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root() / candidate
    return candidate


def models_dir() -> Path:
    """Return the shared models directory, creating it if necessary."""
    target = _path_from_env("ECHOLACE_MODELS_DIR") or repo_root() / "models"
    target.mkdir(parents=True, exist_ok=True)
    return target


def gguf_dir() -> Path:
    """Return the directory that should host GGUF model files."""
    target = _path_from_env("ECHOLACE_GGUF_DIR") or models_dir() / "gguf"
    target.mkdir(parents=True, exist_ok=True)
    return target


def gguf_target_path(filename: str = "model.gguf") -> Path:
    """Return the default GGUF model path."""
    return gguf_dir() / filename


def hf_model_dir(repo_id: Optional[str] = None) -> Path:
    """
    Return the directory for HuggingFace local snapshots.

    If a repo_id is provided, append the sanitized repo folder.
    """
    base = _path_from_env("ECHOLACE_HF_DIR") or models_dir() / "hf"
    base.mkdir(parents=True, exist_ok=True)
    if repo_id:
        sanitized = repo_id.strip("/").split("/")[-1] or "local-model"
        target = base / sanitized
        target.mkdir(parents=True, exist_ok=True)
        return target
    return base
