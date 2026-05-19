# Deployment

This project is designed to be deployed as a **Python library** embedded inside a service (API, agent runtime, or worker),
not as a standalone daemon with its own long-running server process.

The router selects and orchestrates LLM backends based on:
- environment configuration (API keys, model identifiers, local model paths)
- policy engine decisions (privacy, intent routing, hardware telemetry)

## Deployment targets (supported patterns)

### 1) Embed in an existing Python service (recommended)

Install the package (pinned) into your service environment:

- Build + publish internally (or vendor the folder), then:
  - `pip install echolace-llm-router==<version>`

Or for internal mono-repo usage (editable install):

- `pip install -e 03_Production_Applications/Echolace_LLM_Router`

Then instantiate `LLMInterface` where you need it:

```python
from llm_router import LLMInterface

llm = LLMInterface(
    privacy_first=True,
    intent_routing=True,
    hardware_adaptive=True,
)
```

### 2) Containerized service

If your deployment platform is Docker/Kubernetes-based:

- Build a container image for *your service* that includes this package.
- Inject provider credentials via your secret manager (GitHub Environments, Vault, AWS Secrets Manager, etc.).

Minimal runtime requirements are the core deps in `requirements.txt`.
Optional deps can be selected per environment using extras in `pyproject.toml`.

## Required configuration

At minimum you must configure at least one backend.

Common keys:

- OpenAI: `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`)
- Anthropic: `ANTHROPIC_API_KEY` (+ optional `ANTHROPIC_MODEL`)
- Google Gemini: `GOOGLE_API_KEY` (+ optional `GOOGLE_MODEL`)
- HuggingFace API: `HUGGINGFACE_API_KEY` (+ optional `HF_API_MODEL`)
- Universal OpenAI-compatible endpoints: `UNIVERSAL_OPENAI_BASE_URL`, `UNIVERSAL_OPENAI_API_KEY` (+ optional `UNIVERSAL_OPENAI_MODEL`)

Local model paths:
- HF Local: `HF_LOCAL_MODEL`
- HF Image Local: `HF_IMAGE_MODEL`

Model storage helpers:
- `ECHOLACE_MODELS_DIR`, `ECHOLACE_GGUF_DIR`, `ECHOLACE_HF_DIR`

## Release and verification process

This repository tracks a local release evidence convention:

- Evidence folder: `release-evidence/<version>/`

### Manual release verification (local)

From the project root:

- `python -m pip install -r requirements-dev.txt`
- `python -m pip install -e .`
- `python -m black --check .`
- `python -m isort --check-only .`
- `python -m flake8 llm_router tests examples`
- `python -m pytest -q`
- `python -m build`
- `python -m pip_audit -r requirements.txt`

### CI release verification (GitHub Actions)

The workflow `.github/workflows/llm-router-release-verify.yml` supports:

- manual run (`workflow_dispatch`) with an optional version input
- tag-triggered verification for tags matching `llm-router-v*`

It uploads the evidence folder and build artifacts as workflow artifacts.

