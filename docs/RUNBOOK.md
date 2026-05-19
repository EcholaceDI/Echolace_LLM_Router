# Runbook

This runbook captures the day-to-day operations for the Echolace LLM Router.

## Pre-flight

1. Install runtime dependencies:
   ```bash
   pip install -e .
   ```
2. Install development tools for diagnostics:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Confirm universal path helpers are respected via environment overrides:
   - `ECHOLACE_MODELS_DIR` -> root for `models/`.
   - `ECHOLACE_GGUF_DIR` -> GGUF storage.
   - `ECHOLACE_HF_DIR` -> HuggingFace cache root.

## Routine Operations

- **Smoke test**:
  ```bash
  python test_router.py
  ```
  This creates an `LLMInterface`, prints backend diagnostics, and verifies `generate` works via the fallback heuristic backend if no GPU/local models are present.

- **Diagnostics snapshot** (log or alert):
  ```python
  from llm_router import LLMInterface
  llm = LLMInterface()
  print(llm.diagnostics())
  ```

- **Healing plan** (read-only):
  ```python
  plan = llm.heal(apply=False, prefer_local=True)
  print(plan["plan"])
  ```

- **Apply healing** (requires permissions):
  ```python
  llm.heal(
      apply=True,
      allow_network=True,
      install_python_deps=True,
      pull_models=True,
  )
  ```

## Troubleshooting

- `GGUF model file missing`: point `GGUF_MODEL_PATH` at an existing `.gguf` or configure `GGUF_MODEL_URL` and rerun healing.
- `HF_LOCAL_MODEL` warnings: ensure the path exists or set `ECHOLACE_HF_DIR` to a project-local `models/hf`.
- `Dependency install failures`: rerun `python -m pip install` with the package listed in the planner's `install_package` action; check `pip install -r requirements-dev.txt` first.
- `Permission denied on downloads`: confirm `ECHOLACE_GGUF_DIR` is writable or use `ECHOLACE_MODELS_DIR` to redirect to a supported location.

## Health Signals

- Monitor telemetry outputs (`llm.diagnostics()["hardware"]`, `telemetry` module) for latency regressions.
- Ensure `llm.heal()` prompts are reviewed before `apply=True`, especially when pulling remote GGUF or HF snapshots.
