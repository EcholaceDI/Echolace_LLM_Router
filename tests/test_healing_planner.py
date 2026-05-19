import subprocess
from pathlib import Path

import pytest

from llm_router.healing.planner import HealingPlanner
from llm_router.router import LLMInterface


def test_gguf_plan_uses_discovered_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    planner = HealingPlanner()
    model_dir = tmp_path / "models" / "gguf"
    model_dir.mkdir(parents=True)
    model_path = model_dir / "tiny.gguf"
    model_path.write_text("stub", encoding="utf-8")

    monkeypatch.setenv("ECHOLACE_GGUF_DIR", str(model_dir))
    monkeypatch.delenv("GGUF_MODEL_PATH", raising=False)
    monkeypatch.delenv("GGUF_MODEL_URL", raising=False)

    actions = planner.plan(
        [
            {
                "name": "gguf",
                "available": False,
                "diagnostics": {
                    "llama_cpp": "FOUND",
                    "model_path": "MISSING",
                    "model_exists": False,
                },
            }
        ]
    )

    matching = [
        action
        for action in actions
        if action["backend"] == "gguf"
        and action["issue"] == "missing_model_file"
        and action["action"] == "set_environment_variable"
    ]
    assert matching
    assert matching[0]["suggested_value"] == str(model_path.resolve())


def test_gguf_download_workflow_can_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    planner = HealingPlanner()
    target_path = tmp_path / "models" / "gguf" / "downloaded.gguf"

    monkeypatch.setenv("ECHOLACE_GGUF_DIR", str(target_path.parent))
    monkeypatch.setenv("GGUF_MODEL_PATH", str(target_path))
    monkeypatch.setenv("GGUF_MODEL_URL", "https://example.com/model.gguf")

    actions = planner.plan(
        [
            {
                "name": "gguf",
                "available": False,
                "diagnostics": {
                    "llama_cpp": "FOUND",
                    "model_path": str(target_path),
                    "model_exists": False,
                },
            }
        ]
    )
    download = next(
        action for action in actions if action["action"] == "download_model"
    )

    def fake_urlretrieve(url: str, destination: str):
        Path(destination).write_bytes(b"gguf-bytes")
        return destination, None

    monkeypatch.setattr("urllib.request.urlretrieve", fake_urlretrieve)

    result = planner.apply(
        [download],
        allow_network=True,
        install_python_deps=False,
        pull_models=True,
    )

    assert result["applied"]
    assert target_path.read_bytes() == b"gguf-bytes"


def test_hf_local_plan_includes_dependency_and_snapshot_remediation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner = HealingPlanner()
    monkeypatch.delenv("HF_LOCAL_MODEL", raising=False)
    monkeypatch.setenv("HF_LOCAL_REPO_ID", "acme/test-model")

    actions = planner.plan(
        [
            {
                "name": "hf_local",
                "available": False,
                "diagnostics": {
                    "transformers": "MISSING",
                    "torch": "MISSING",
                    "model_path": "MISSING",
                    "model_exists": False,
                },
            }
        ]
    )

    action_types = {(action["action"], action.get("package")) for action in actions}
    assert ("install_package", "transformers") in action_types
    assert ("install_package", "torch") in action_types
    assert any(action["action"] == "download_hf_snapshot" for action in actions)


def test_lmstudio_plan_surfaces_model_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner = HealingPlanner()
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)

    actions = planner.plan(
        [
            {
                "name": "lmstudio",
                "available": False,
                "diagnostics": {
                    "status": "reachable",
                    "models": [{"id": "qwen2.5-7b-instruct"}],
                },
            }
        ]
    )

    model_actions = [
        action
        for action in actions
        if action["action"] == "set_environment_variable"
        and action.get("env_var") == "LMSTUDIO_MODEL"
    ]
    assert model_actions
    assert model_actions[0]["suggested_value"] == "qwen2.5-7b-instruct"


def test_apply_retries_retryable_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    planner = HealingPlanner()
    calls = {"count": 0}

    def fake_run(command, capture_output, text, check):
        calls["count"] += 1
        if calls["count"] == 1:
            return subprocess.CompletedProcess(command, 1, "", "temporary failure")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = planner.apply(
        [
            {
                "backend": "ollama",
                "issue": "model_missing",
                "action": "pull_model",
                "command": ["ollama", "pull", "phi3"],
                "requires_network": True,
                "retryable": True,
            }
        ],
        allow_network=True,
        install_python_deps=False,
        pull_models=True,
    )

    assert not result["failed"]
    assert result["applied"][0]["attempts"] == 2


def test_router_heal_preserves_public_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "llm_router.router.diagnostics_heal",
        lambda **kwargs: {
            "healthy": False,
            "selected_backend": kwargs.get("backend"),
            "issues": [],
            "plan": [],
            "applied": [],
            "skipped": [],
            "failed": [],
            "prompts": [{"backend": "gguf", "prompt": "Download now?"}],
            "hardware": {},
        },
    )

    llm = LLMInterface(provider="heuristic")
    result = llm.heal(backend="gguf")

    assert "prompts" in result
    assert result["selected_backend"] == "gguf"
