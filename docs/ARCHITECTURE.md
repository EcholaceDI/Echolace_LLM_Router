# Architecture Overview

The Echolace LLM Router routes prompts to the most appropriate backend using layered policy, privacy, telemetry, and healing safeguards. Each component is intentionally small and testable.

## Core Components

- **LLMInterface / router.py** – The entry point that discovers available backends (`llm_router.__all__`), evaluates routing policies, and exposes `generate`, `stream`, `intent`, `diagnostics`, and `heal`.
- **Policy layer** – Encapsulates routing strategies (e.g., hardware-aware downgrading, privacy-first evaluation, intent-based provider selection) before any backend is invoked.
- **Privacy layer (privacy.py)** – Scans prompts and structured payloads for PII and secrets, optionally redacting or forcing local execution before routing decisions are made.
- **Telemetry (telemetry module)** – Samples CPU/GPU, tracks latency/TTFT, and records queue depth so the router can downgrade gracefully (`hardware_adaptive=True`).
- **Healing planner (healing/planner.py)** – Looks at diagnostics, available models, and environment hints to suggest actionable repair steps (install packages, download GGUF, point GPT4All, etc.).
- **Providers** – Each backend (`providers/*`) owns its own availability checks, diagnostics, and streaming logic while inheriting from `LLMBackend`.

## Universal Pathing (llm_router.paths)

All storage paths are computed through `llm_router.paths` so the router never hardcodes machine-specific directories:

- `repo_root()` anchors helpers to the `Echolace_LLM_Router` folder.
- `models_dir()` always lives under `models/` (or `ECHOLACE_MODELS_DIR`) and is created on demand.
- `gguf_dir()` and `gguf_target_path()` center GGUF workflows in a predictable subfolder.
- `hf_model_dir(repo_id)` scopes HuggingFace snapshots under `models/hf/<repo_id>` (or `ECHOLACE_HF_DIR`), letting healing/download workflows run deterministically on Windows and POSIX.

## Data Flow

1. The router collects backend diagnostics via each provider's `diagnose()` method.
2. Policies (`llm_router.policies`, `llm_router.intent`) score the prompt and decide whether to consult privacy, prefer local, or offload to cloud.
3. Telemetry and hardware-aware heuristics may adjust the chosen backend before `generate()`/`stream()` is invoked.
4. If a backend fails, `HealingPlanner` proposes steps that reference the universal path helpers to download models or set environment variables.

This modular layout keeps the router reliable and makes CI/test coverage straightforward.
