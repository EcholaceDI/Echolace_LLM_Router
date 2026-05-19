import importlib.util
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..paths import gguf_dir, gguf_target_path, hf_model_dir, models_dir


@dataclass
class RepairAction:
    backend: str
    issue: str
    action: str
    severity: str = "warning"
    package: Optional[str] = None
    env_var: Optional[str] = None
    model: Optional[str] = None
    command: Optional[List[str]] = None
    requires_network: bool = False
    auto_applicable: bool = False
    approval_required: bool = True
    reversible: bool = True
    retryable: bool = False
    title: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    suggested_value: Optional[str] = None
    target_path: Optional[str] = None
    download_url: Optional[str] = None
    source_repo: Optional[str] = None
    discovered_models: List[Dict[str, Any]] = field(default_factory=list)
    manual_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "backend": self.backend,
            "issue": self.issue,
            "action": self.action,
            "severity": self.severity,
            "package": self.package,
            "env_var": self.env_var,
            "model": self.model,
            "command": self.command,
            "requires_network": self.requires_network,
            "auto_applicable": self.auto_applicable,
            "approval_required": self.approval_required,
            "reversible": self.reversible,
            "retryable": self.retryable,
            "title": self.title,
            "description": self.description,
            "prompt": self.prompt,
            "suggested_value": self.suggested_value,
            "target_path": self.target_path,
            "download_url": self.download_url,
            "source_repo": self.source_repo,
            "discovered_models": self.discovered_models,
            "manual_steps": self.manual_steps,
        }
        return {
            key: value for key, value in payload.items() if value not in (None, [], {})
        }


class HealingPlanner:
    def __init__(self, prefer_local: bool = True):
        self.prefer_local = prefer_local

    def plan(
        self,
        backends: List[Dict[str, Any]],
        prefer_local: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        prefer_local = self.prefer_local if prefer_local is None else prefer_local
        actions: List[Dict[str, Any]] = []
        for backend in backends:
            actions.extend(
                self._actions_for_backend(backend, prefer_local=prefer_local)
            )
        return actions

    def apply(
        self,
        actions: List[Dict[str, Any]],
        allow_network: bool,
        install_python_deps: bool,
        pull_models: bool,
    ) -> Dict[str, List[Dict[str, Any]]]:
        applied: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        for action in actions:
            result = self._apply_action(
                action,
                allow_network=allow_network,
                install_python_deps=install_python_deps,
                pull_models=pull_models,
            )
            if result["status"] == "applied":
                applied.append(result)
            elif result["status"] == "failed":
                failed.append(result)
            else:
                skipped.append(result)
        return {
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
        }

    def _actions_for_backend(
        self,
        backend_report: Dict[str, Any],
        prefer_local: bool,
    ) -> List[Dict[str, Any]]:
        backend_name = backend_report["name"]
        diagnostics = backend_report.get("diagnostics", {})
        actions: List[RepairAction] = []

        for package in self._package_hints().get(backend_name, []):
            if self._is_package_missing(diagnostics, package):
                actions.append(
                    RepairAction(
                        backend=backend_name,
                        issue="missing_dependency",
                        action="install_package",
                        package=package,
                        command=[sys.executable, "-m", "pip", "install", package],
                        requires_network=True,
                        auto_applicable=True,
                        approval_required=True,
                        reversible=False,
                        retryable=True,
                        title=f"Install {package}",
                        description=f"Install the missing Python dependency required by the {backend_name} backend.",
                        prompt=f"Allow installing `{package}` for the `{backend_name}` backend?",
                    )
                )

        actions.extend(self._env_actions_for_backend(backend_name))

        if backend_name == "gguf":
            actions.extend(self._gguf_actions(diagnostics))
        elif backend_name == "ollama":
            actions.extend(self._ollama_actions(diagnostics, prefer_local))
        elif backend_name == "lmstudio":
            actions.extend(self._lmstudio_actions(diagnostics))
        elif backend_name == "gpt4all":
            actions.extend(self._gpt4all_actions(diagnostics))
        elif backend_name == "hf_local":
            actions.extend(self._hf_local_actions(diagnostics))

        return [action.to_dict() for action in actions]

    def _env_actions_for_backend(self, backend_name: str) -> List[RepairAction]:
        actions: List[RepairAction] = []
        handled_by_backend = {
            "gguf": {"GGUF_MODEL_PATH"},
            "ollama": {"OLLAMA_MODEL"},
            "lmstudio": {"LMSTUDIO_MODEL"},
            "gpt4all": {"GPT4ALL_MODEL"},
            "hf_local": {"HF_LOCAL_MODEL"},
        }
        for env_var in self._env_hints().get(backend_name, []):
            if env_var in handled_by_backend.get(backend_name, set()):
                continue
            if self._is_env_missing(env_var):
                actions.append(
                    RepairAction(
                        backend=backend_name,
                        issue="missing_configuration",
                        action="set_environment_variable",
                        env_var=env_var,
                        auto_applicable=False,
                        approval_required=True,
                        title=f"Set {env_var}",
                        description=f"Configure `{env_var}` so the `{backend_name}` backend knows which model or endpoint to use.",
                        prompt=f"Set `{env_var}` before retrying `{backend_name}`?",
                    )
                )
        return actions

    def _gguf_actions(self, diagnostics: Dict[str, Any]) -> List[RepairAction]:
        actions: List[RepairAction] = []
        configured_path = os.getenv("GGUF_MODEL_PATH")
        model_exists = bool(diagnostics.get("model_exists"))
        discovered = self._discover_gguf_models(diagnostics)

        if configured_path and model_exists:
            return actions

        if discovered:
            suggested = discovered[0]["path"]
            actions.append(
                RepairAction(
                    backend="gguf",
                    issue="missing_model_file",
                    action="set_environment_variable",
                    env_var="GGUF_MODEL_PATH",
                    suggested_value=suggested,
                    discovered_models=discovered,
                    title="Point GGUF backend at a discovered model",
                    description="A local GGUF model file was found on disk and can be used immediately.",
                    prompt="Use one of the discovered GGUF files for `GGUF_MODEL_PATH`?",
                    manual_steps=[
                        f"Set GGUF_MODEL_PATH={suggested}",
                        "Retry llm.heal() or create a new LLMInterface instance.",
                    ],
                )
            )
            return actions

        download_url = os.getenv("GGUF_MODEL_URL")
        target_path = configured_path or self._default_gguf_target_path()
        if download_url:
            actions.append(
                RepairAction(
                    backend="gguf",
                    issue="missing_model_file",
                    action="download_model",
                    env_var="GGUF_MODEL_PATH",
                    model=os.path.basename(target_path),
                    target_path=target_path,
                    download_url=download_url,
                    requires_network=True,
                    auto_applicable=True,
                    approval_required=True,
                    reversible=True,
                    retryable=True,
                    title="Fetch configured GGUF model",
                    description="Download the GGUF model to the configured path using `GGUF_MODEL_URL`.",
                    prompt="Download the GGUF model file now?",
                    manual_steps=[
                        "Verify the URL in GGUF_MODEL_URL resolves to a .gguf file.",
                        f"Confirm the destination path {target_path} is correct.",
                    ],
                )
            )
        else:
            actions.append(
                RepairAction(
                    backend="gguf",
                    issue="missing_model_file",
                    action="prepare_model_fetch",
                    env_var="GGUF_MODEL_URL",
                    target_path=target_path,
                    title="Prepare a GGUF download workflow",
                    description="No local GGUF model was discovered. Provide a model URL or place a .gguf file on disk.",
                    prompt="Set `GGUF_MODEL_URL` or place a GGUF file locally before retrying.",
                    manual_steps=[
                        f"Place a .gguf file at {target_path} and set GGUF_MODEL_PATH={target_path}",
                        "Or set GGUF_MODEL_URL to a direct model download URL, then rerun llm.heal(apply=True, allow_network=True, pull_models=True).",
                    ],
                )
            )
        return actions

    def _ollama_actions(
        self,
        diagnostics: Dict[str, Any],
        prefer_local: bool,
    ) -> List[RepairAction]:
        actions: List[RepairAction] = []
        configured_model = os.getenv("OLLAMA_MODEL") or (
            "phi3" if prefer_local else None
        )
        discovered = self._discover_runtime_models("ollama", diagnostics)
        discovered_names = {item["name"] for item in discovered}

        if diagnostics.get("status") == "unreachable":
            actions.append(
                RepairAction(
                    backend="ollama",
                    issue="server_unreachable",
                    action="start_local_service",
                    command=["ollama", "serve"],
                    auto_applicable=False,
                    approval_required=True,
                    title="Start the Ollama service",
                    description="Ollama is installed but the local HTTP service is not reachable.",
                    prompt="Start the Ollama server, then retry the request?",
                    manual_steps=["Run `ollama serve` in a separate terminal."],
                )
            )

        if configured_model and configured_model not in discovered_names:
            actions.append(
                RepairAction(
                    backend="ollama",
                    issue="model_missing",
                    action="pull_model",
                    model=configured_model,
                    command=["ollama", "pull", configured_model],
                    requires_network=True,
                    auto_applicable=True,
                    approval_required=True,
                    retryable=True,
                    title=f"Pull Ollama model {configured_model}",
                    description="The configured Ollama model is not present locally.",
                    prompt=f"Download `{configured_model}` into Ollama now?",
                )
            )

        if not configured_model and discovered:
            actions.append(
                RepairAction(
                    backend="ollama",
                    issue="missing_configuration",
                    action="set_environment_variable",
                    env_var="OLLAMA_MODEL",
                    suggested_value=discovered[0]["name"],
                    discovered_models=discovered,
                    title="Set a default Ollama model",
                    description="Ollama is reachable but no default model is configured for the router.",
                    prompt="Choose one of the discovered Ollama models for `OLLAMA_MODEL`.",
                )
            )
        return actions

    def _lmstudio_actions(self, diagnostics: Dict[str, Any]) -> List[RepairAction]:
        actions: List[RepairAction] = []
        discovered = self._discover_runtime_models("lmstudio", diagnostics)
        configured_model = os.getenv("LMSTUDIO_MODEL")
        discovered_names = {item["name"] for item in discovered}

        if diagnostics.get("status") == "unreachable":
            actions.append(
                RepairAction(
                    backend="lmstudio",
                    issue="server_unreachable",
                    action="open_application",
                    severity="info",
                    title="Open LM Studio and enable the server",
                    description="LM Studio is GUI-driven. The router could not reach its OpenAI-compatible local server.",
                    prompt="Open LM Studio, load a model, and enable the OpenAI-compatible server?",
                    manual_steps=[
                        "Open LM Studio.",
                        "Load a model into memory.",
                        "Enable the OpenAI-compatible server in LM Studio.",
                    ],
                )
            )

        if discovered and (
            not configured_model or configured_model not in discovered_names
        ):
            actions.append(
                RepairAction(
                    backend="lmstudio",
                    issue="model_selection_required",
                    action="set_environment_variable",
                    env_var="LMSTUDIO_MODEL",
                    suggested_value=discovered[0]["name"],
                    discovered_models=discovered,
                    title="Choose a loaded LM Studio model",
                    description="LM Studio is exposing models, but the router does not have a stable default model configured.",
                    prompt="Set `LMSTUDIO_MODEL` to one of the discovered LM Studio model IDs?",
                )
            )
        elif not discovered:
            actions.append(
                RepairAction(
                    backend="lmstudio",
                    issue="no_models_loaded",
                    action="load_model_in_ui",
                    severity="info",
                    title="Load a model in LM Studio",
                    description="LM Studio is reachable but is not currently serving any loaded model.",
                    prompt="Load a model inside LM Studio and retry.",
                )
            )
        return actions

    def _gpt4all_actions(self, diagnostics: Dict[str, Any]) -> List[RepairAction]:
        actions: List[RepairAction] = []
        discovered = self._discover_runtime_models("gpt4all", diagnostics)
        configured_model = os.getenv("GPT4ALL_MODEL")
        discovered_names = {item["name"] for item in discovered}

        if diagnostics.get("status") == "unreachable":
            command = ["gpt4all", "--server"]
            if configured_model:
                command.extend(["--model", configured_model])
            actions.append(
                RepairAction(
                    backend="gpt4all",
                    issue="server_unreachable",
                    action="start_local_service",
                    command=command,
                    auto_applicable=False,
                    approval_required=True,
                    title="Start the GPT4All server",
                    description="GPT4All is not reachable on its local API port.",
                    prompt="Start GPT4All in server mode before retrying?",
                    manual_steps=["Run `gpt4all --server --model <model.gguf>`."],
                )
            )

        if discovered and (
            not configured_model or configured_model not in discovered_names
        ):
            actions.append(
                RepairAction(
                    backend="gpt4all",
                    issue="model_selection_required",
                    action="set_environment_variable",
                    env_var="GPT4ALL_MODEL",
                    suggested_value=discovered[0]["name"],
                    discovered_models=discovered,
                    title="Choose a GPT4All model",
                    description="GPT4All exposed available models, but the router does not have a default model configured.",
                    prompt="Set `GPT4ALL_MODEL` to one of the discovered GPT4All model IDs?",
                )
            )
        elif not discovered:
            gguf_candidates = self._discover_gguf_models({})
            if gguf_candidates:
                actions.append(
                    RepairAction(
                        backend="gpt4all",
                        issue="model_selection_required",
                        action="set_environment_variable",
                        env_var="GPT4ALL_MODEL",
                        suggested_value=gguf_candidates[0]["path"],
                        discovered_models=gguf_candidates,
                        title="Use a discovered GGUF file with GPT4All",
                        description="A GGUF file was found locally and can be used when starting the GPT4All server.",
                        prompt="Point GPT4All at one of the discovered GGUF files?",
                    )
                )
        return actions

    def _hf_local_actions(self, diagnostics: Dict[str, Any]) -> List[RepairAction]:
        actions: List[RepairAction] = []
        discovered = self._discover_hf_local_models(diagnostics)
        configured_model = os.getenv("HF_LOCAL_MODEL")
        model_exists = bool(diagnostics.get("model_exists"))

        if configured_model and model_exists:
            return actions

        if discovered:
            actions.append(
                RepairAction(
                    backend="hf_local",
                    issue="missing_model_file",
                    action="set_environment_variable",
                    env_var="HF_LOCAL_MODEL",
                    suggested_value=discovered[0]["path"],
                    discovered_models=discovered,
                    title="Use a discovered local Hugging Face model",
                    description="A local model directory with `config.json` was found and can be used by the Hugging Face local backend.",
                    prompt="Set `HF_LOCAL_MODEL` to one of the discovered model directories?",
                )
            )
            return actions

        repo_id = os.getenv("HF_LOCAL_REPO_ID")
        target_path = configured_model or self._default_hf_local_target_path(repo_id)
        if repo_id:
            actions.append(
                RepairAction(
                    backend="hf_local",
                    issue="missing_model_file",
                    action="download_hf_snapshot",
                    env_var="HF_LOCAL_MODEL",
                    source_repo=repo_id,
                    target_path=target_path,
                    package="huggingface_hub",
                    requires_network=True,
                    auto_applicable=True,
                    approval_required=True,
                    retryable=True,
                    title=f"Download Hugging Face model snapshot for {repo_id}",
                    description="Download the configured repository snapshot into a local directory for the HF local backend.",
                    prompt=f"Download `{repo_id}` into `{target_path}` now?",
                )
            )
        else:
            actions.append(
                RepairAction(
                    backend="hf_local",
                    issue="missing_model_file",
                    action="prepare_model_fetch",
                    env_var="HF_LOCAL_REPO_ID",
                    target_path=target_path,
                    title="Configure a local Hugging Face model source",
                    description="No local model directory was found. Set `HF_LOCAL_REPO_ID` or place a model directory on disk.",
                    prompt="Set `HF_LOCAL_REPO_ID` or `HF_LOCAL_MODEL`, then rerun llm.heal().",
                )
            )
        return actions

    def _apply_action(
        self,
        action: Dict[str, Any],
        allow_network: bool,
        install_python_deps: bool,
        pull_models: bool,
    ) -> Dict[str, Any]:
        result = dict(action)
        result.setdefault("attempts", 0)

        if action["action"] == "install_package":
            if not install_python_deps:
                return self._skip(result, "install_python_deps_disabled")
            if action.get("requires_network") and not allow_network:
                return self._skip(result, "allow_network_disabled")
            return self._run_command(result, action.get("command"))

        if action["action"] == "pull_model":
            if not pull_models:
                return self._skip(result, "pull_models_disabled")
            if action.get("requires_network") and not allow_network:
                return self._skip(result, "allow_network_disabled")
            return self._run_command(result, action.get("command"))

        if action["action"] == "download_model":
            if not pull_models:
                return self._skip(result, "pull_models_disabled")
            if action.get("requires_network") and not allow_network:
                return self._skip(result, "allow_network_disabled")
            return self._download_model(result)

        if action["action"] == "download_hf_snapshot":
            if not pull_models:
                return self._skip(result, "pull_models_disabled")
            if action.get("requires_network") and not allow_network:
                return self._skip(result, "allow_network_disabled")
            return self._download_hf_snapshot(
                result, install_python_deps=install_python_deps
            )

        return self._skip(result, "manual_action_required")

    def _run_command(
        self,
        action: Dict[str, Any],
        command: Optional[List[str]],
    ) -> Dict[str, Any]:
        if not command:
            return self._skip(action, "missing_command")

        max_attempts = 2 if action.get("retryable") else 1
        completed = None
        last_stdout = ""
        last_stderr = ""
        for attempt in range(1, max_attempts + 1):
            action["attempts"] = attempt
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as exc:
                if attempt == max_attempts:
                    action["status"] = "failed"
                    action["error"] = str(exc)
                    action["next_steps"] = [
                        "Retry the command manually after reviewing the environment."
                    ]
                    return action
                continue

            last_stdout = completed.stdout.strip()
            last_stderr = completed.stderr.strip()
            if completed.returncode == 0:
                action["status"] = "applied"
                action["returncode"] = completed.returncode
                action["stdout"] = last_stdout
                action["stderr"] = last_stderr
                return action

        action["status"] = "failed"
        action["returncode"] = completed.returncode if completed is not None else None
        action["stdout"] = last_stdout
        action["stderr"] = last_stderr
        action["next_steps"] = [
            "Review the command output and retry once the backend is reachable."
        ]
        return action

    def _download_model(self, action: Dict[str, Any]) -> Dict[str, Any]:
        url = action.get("download_url")
        target_path = action.get("target_path")
        if not url or not target_path:
            return self._skip(action, "missing_download_metadata")

        destination = Path(target_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            suffix=destination.suffix or ".tmp",
            dir=str(destination.parent),
        )
        os.close(handle)
        try:
            action["attempts"] = 1
            urllib.request.urlretrieve(url, temp_name)
            os.replace(temp_name, destination)
            action["status"] = "applied"
            action["downloaded_to"] = str(destination)
            return action
        except Exception as exc:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            action["status"] = "failed"
            action["error"] = str(exc)
            action["next_steps"] = [
                "Verify the model URL and available disk space, then retry."
            ]
            return action

    def _download_hf_snapshot(
        self,
        action: Dict[str, Any],
        *,
        install_python_deps: bool,
    ) -> Dict[str, Any]:
        if importlib.util.find_spec("huggingface_hub") is None:
            if not install_python_deps:
                return self._skip(action, "huggingface_hub_missing")
            install_result = self._run_command(
                {
                    "backend": action["backend"],
                    "action": "install_package",
                    "package": "huggingface_hub",
                    "command": [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "huggingface_hub",
                    ],
                    "retryable": True,
                },
                [sys.executable, "-m", "pip", "install", "huggingface_hub"],
            )
            if install_result.get("status") != "applied":
                action["status"] = "failed"
                action["error"] = "Failed to install huggingface_hub"
                return action

        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:
            action["status"] = "failed"
            action["error"] = str(exc)
            return action

        repo_id = action.get("source_repo")
        target_path = action.get("target_path")
        if not repo_id or not target_path:
            return self._skip(action, "missing_download_metadata")

        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            action["attempts"] = 1
            snapshot_download(
                repo_id=repo_id,
                local_dir=target_path,
                local_dir_use_symlinks=False,
            )
            action["status"] = "applied"
            action["downloaded_to"] = target_path
            return action
        except Exception as exc:
            action["status"] = "failed"
            action["error"] = str(exc)
            action["next_steps"] = [
                "Verify HF_LOCAL_REPO_ID, network access, and authentication if required."
            ]
            return action

    def _skip(self, action: Dict[str, Any], reason: str) -> Dict[str, Any]:
        action["status"] = "skipped"
        action["reason"] = reason
        return action

    def _discover_runtime_models(
        self,
        backend_name: str,
        diagnostics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        models = diagnostics.get("models", [])
        discovered: List[Dict[str, Any]] = []
        for model in models:
            name = None
            if isinstance(model, dict):
                name = model.get("name") or model.get("id") or model.get("model")
            elif isinstance(model, str):
                name = model
            if name:
                discovered.append(
                    {
                        "name": str(name),
                        "source": f"{backend_name}_runtime",
                    }
                )
        return discovered

    def _discover_gguf_models(
        self, diagnostics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        candidates: List[Path] = []
        configured = diagnostics.get("model_path")
        if configured and configured != "MISSING":
            candidates.append(Path(str(configured)))

        env_file = os.getenv("GGUF_MODEL_PATH")
        if env_file:
            candidates.append(Path(env_file))

        search_roots = [
            os.getenv("GGUF_MODEL_DIR"),
            os.getenv("ECHOLACE_GGUF_DIR"),
            gguf_dir(),
            models_dir(),
            self._local_appdata_path("nomic.ai", "GPT4All"),
            self._local_appdata_path("LM Studio", "models"),
        ]
        for root in search_roots:
            if not root:
                continue
            root_path = Path(root)
            if root_path.is_file():
                candidates.append(root_path)
                continue
            if not root_path.exists():
                continue
            candidates.extend(root_path.glob("*.gguf"))
            candidates.extend(root_path.rglob("*.gguf"))

        return self._dedupe_discovered_paths(candidates, source="filesystem")

    def _discover_hf_local_models(
        self, diagnostics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        candidates: List[Path] = []
        configured = diagnostics.get("model_path")
        if configured and configured != "MISSING":
            candidates.append(Path(str(configured)))

        env_file = os.getenv("HF_LOCAL_MODEL")
        if env_file:
            candidates.append(Path(env_file))

        search_roots = [
            os.getenv("HF_HOME"),
            Path.cwd() / "models",
            Path.cwd() / "models" / "hf",
        ]
        for root in search_roots:
            if not root:
                continue
            root_path = Path(root)
            if not root_path.exists():
                continue
            if root_path.is_dir() and (root_path / "config.json").exists():
                candidates.append(root_path)
            for child in root_path.iterdir():
                if child.is_dir() and (child / "config.json").exists():
                    candidates.append(child)

        return self._dedupe_discovered_paths(candidates, source="filesystem")

    def _dedupe_discovered_paths(
        self,
        paths: Iterable[Path],
        *,
        source: str,
    ) -> List[Dict[str, Any]]:
        seen = set()
        discovered: List[Dict[str, Any]] = []
        for path in paths:
            try:
                resolved = str(path.resolve())
            except Exception:
                resolved = str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            if not Path(resolved).exists():
                continue
            discovered.append(
                {
                    "name": Path(resolved).name,
                    "path": resolved,
                    "source": source,
                }
            )
        return discovered[:20]

    def _default_gguf_target_path(self) -> str:
        return str(gguf_target_path())

    def _default_hf_local_target_path(self, repo_id: Optional[str]) -> str:
        return str(hf_model_dir(repo_id))

    def _local_appdata_path(self, *parts: str) -> Optional[Path]:
        for env_var in ("LOCALAPPDATA", "XDG_DATA_HOME"):
            root = os.getenv(env_var)
            if root:
                return Path(root).expanduser().joinpath(*parts)

        fallback = Path.home() / ".local" / "share"
        return fallback.joinpath(*parts)

    def _package_hints(self) -> Dict[str, List[str]]:
        return {
            "anthropic": ["anthropic"],
            "google": ["google-generativeai"],
            "hf_api": ["huggingface_hub"],
            "hf_local": ["transformers", "torch"],
            "openai_standard": ["openai"],
            "openai_streaming": ["openai"],
            "gguf": ["llama-cpp-python"],
        }

    def _env_hints(self) -> Dict[str, List[str]]:
        return {
            "anthropic": ["ANTHROPIC_API_KEY"],
            "google": ["GOOGLE_API_KEY"],
            "hf_api": ["HUGGINGFACE_API_KEY", "HF_API_KEY"],
            "hf_local": ["HF_LOCAL_MODEL"],
            "openai_standard": ["OPENAI_API_KEY"],
            "openai_streaming": ["OPENAI_API_KEY"],
            "openai_universal": ["UNIVERSAL_OPENAI_BASE_URL"],
            "gguf": ["GGUF_MODEL_PATH"],
            "ollama": ["OLLAMA_MODEL"],
            "lmstudio": ["LMSTUDIO_MODEL"],
            "gpt4all": ["GPT4ALL_MODEL"],
        }

    def _is_package_missing(self, diagnostics: Dict[str, Any], package: str) -> bool:
        package_key = package.replace("-", "_")
        for key, value in diagnostics.items():
            normalized = str(value).upper()
            if package_key in key.lower() and normalized == "MISSING":
                return True
            if (
                package == "google-generativeai"
                and key == "library"
                and normalized == "MISSING"
            ):
                return True
            if (
                package == "huggingface_hub"
                and key == "library"
                and normalized == "MISSING"
            ):
                return True
            if (
                package == "llama-cpp-python"
                and key == "llama_cpp"
                and normalized == "MISSING"
            ):
                return True
            if (
                package == "transformers"
                and key == "transformers"
                and normalized == "MISSING"
            ):
                return True
            if package == "torch" and key == "torch" and normalized == "MISSING":
                return True
            if (
                package == "openai"
                and key == "openai_library"
                and normalized == "MISSING"
            ):
                return True
        return False

    def _is_env_missing(self, env_var: str) -> bool:
        if env_var == "HF_API_KEY":
            return not (os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY"))
        value = os.getenv(env_var)
        return value is None or value == ""


__all__ = ["HealingPlanner", "RepairAction"]
