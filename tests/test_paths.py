from pathlib import Path

import pytest

from llm_router.paths import gguf_dir, gguf_target_path, hf_model_dir, models_dir


def test_models_dir_respects_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_dir = tmp_path / "custom-models"
    monkeypatch.setenv("ECHOLACE_MODELS_DIR", str(custom_dir))

    assert models_dir() == custom_dir
    assert custom_dir.exists()


def test_models_dir_handles_windows_style_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    windows_style = str(tmp_path / "windows" / "models").replace("/", "\\")
    monkeypatch.setenv("ECHOLACE_MODELS_DIR", windows_style)

    expected = Path(str(tmp_path / "windows" / "models"))
    assert models_dir() == expected
    assert expected.exists()


def test_gguf_dir_defaults_to_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLACE_MODELS_DIR", str(tmp_path))
    monkeypatch.delenv("ECHOLACE_GGUF_DIR", raising=False)

    result = gguf_dir()
    assert result == tmp_path / "gguf"
    assert result.exists()


def test_gguf_target_path_uses_gguf_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLACE_MODELS_DIR", str(tmp_path))
    monkeypatch.delenv("ECHOLACE_GGUF_DIR", raising=False)

    target = gguf_target_path("download.gguf")
    assert target == tmp_path / "gguf" / "download.gguf"


def test_hf_model_dir_appends_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ECHOLACE_MODELS_DIR", str(tmp_path))
    repo_path = hf_model_dir("acme/test-model")

    assert repo_path == tmp_path / "hf" / "test-model"
    assert repo_path.exists()
