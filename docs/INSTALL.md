# Installation Guide

This guide reflects the current package and backend configuration in the repository.
The router keeps installation explicit by default: it does not mutate your environment unless you call `llm.heal(..., apply=True, ...)` with the required permission flags.

## Requirements

- Python 3.8 or newer
- `pip` or `uv`
- optional local runtime software depending on backend:
  - Ollama
  - LM Studio
  - GPT4All server mode

## Core Install

With `pip`:

```bash
pip install echolace-llm-router
```

With `uv`:

```bash
uv pip install echolace-llm-router
```

## Optional Extras

The package defines these extras in `pyproject.toml`:

```bash
pip install echolace-llm-router[privacy]
pip install echolace-llm-router[intent]
pip install echolace-llm-router[telemetry]
pip install echolace-llm-router[local]
pip install echolace-llm-router[all]
```

What they include:

- `privacy`
  - `presidio-analyzer`
  - `cryptography`
- `intent`
  - `sentence-transformers`
  - `scikit-learn`
- `telemetry`
  - `psutil`
- `local`
  - `transformers`
  - `torch`
  - `llama-cpp-python`
  - `gpt4all`
  - `lmstudio`

## Backend Setup

### Anthropic

```bash
pip install anthropic
```

Set:

```bash
export ANTHROPIC_API_KEY="your-key"
```

### OpenAI standard and streaming

```bash
pip install openai
```

Set:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-4o-mini"
```

Azure OpenAI is supported by `openai_standard` with:

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment"
```

### OpenAI-compatible universal backend

No extra SDK is required beyond `requests`, which is part of the core package.

Set:

```bash
export UNIVERSAL_OPENAI_BASE_URL="http://localhost:8000/v1"
export UNIVERSAL_OPENAI_API_KEY="optional-key"
export UNIVERSAL_OPENAI_MODEL="gpt-4o-mini"
```

### Google Gemini

```bash
pip install google-generativeai
```

Set:

```bash
export GOOGLE_API_KEY="your-key"
export GOOGLE_MODEL="gemini-1.5-pro-latest"
```

### Hugging Face API

```bash
pip install huggingface_hub
```

Set:

```bash
export HUGGINGFACE_API_KEY="your-key"
export HF_API_MODEL="mistralai/Mistral-7B-Instruct-v0.2"
```

### Hugging Face local

```bash
pip install transformers torch
```

Set:

```bash
export HF_LOCAL_MODEL="/path/to/local/model-directory"
```

The configured directory must exist locally.

### GGUF

```bash
pip install llama-cpp-python
```

Set:

```bash
export GGUF_MODEL_PATH="/path/to/model.gguf"
```

Optional healing/download helpers:

```bash
export GGUF_MODEL_URL="https://example.com/model.gguf"
export GGUF_MODEL_DIR="/path/to/search-directory"
```

### Universal Path Overrides

- `ECHOLACE_MODELS_DIR` overrides the repository `models/` root used by healing and downloads.
- `ECHOLACE_GGUF_DIR` keeps GGUF artifacts in a predictable subfolder without hard-coded machine paths.
- `ECHOLACE_HF_DIR` points to the HuggingFace snapshot root (the planner appends the repo ID automatically).
- These helpers keep CI/self-hosted runs deterministic while still honoring legacy vars like `GGUF_MODEL_DIR`.

### GPT4All

The current backend expects a reachable local GPT4All HTTP server.

Set if needed:

```bash
export GPT4ALL_BASE_URL="http://localhost:4891/v1"
export GPT4ALL_MODEL="path-or-model-id"
```

### LM Studio

The current backend expects LM Studio's OpenAI-compatible local server.

Set if needed:

```bash
export LMSTUDIO_BASE_URL="http://localhost:1234/v1"
export LMSTUDIO_MODEL="loaded-model-id"
```

You must also:

1. Open LM Studio.
2. Load a model into memory.
3. Enable the OpenAI-compatible server.

### Ollama

Set if needed:

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="phi3"
```

Typical runtime commands:

```bash
ollama serve
ollama pull phi3
```

## Verifying The Installation

Basic router check:

```python
from llm_router import LLMInterface

llm = LLMInterface()
print(llm.info())
print(llm.available_backends())
```

Diagnostics check:

```python
report = llm.diagnostics()
print(report["backends"])
```

Healing plan only:

```python
repair = llm.heal(
    apply=False,
    prefer_local=True,
)
print(repair["plan"])
print(repair["prompts"])
```

Healing with explicit action flags:

```python
repair = llm.heal(
    apply=True,
    allow_network=True,
    install_python_deps=True,
    pull_models=True,
    prefer_local=True,
)
```

Notes:

- networked actions are skipped unless `allow_network=True`
- package installs are skipped unless `install_python_deps=True`
- model pulls and downloads are skipped unless `pull_models=True`

## Recommended Local-First Setup

If you want privacy-aware routing with local fallback:

1. Install `telemetry`, `privacy`, and at least one local runtime.
2. Configure a local backend such as Ollama or GGUF.
3. Start with:

```python
llm = LLMInterface(
    privacy_first=True,
    hardware_adaptive=True,
    local_privacy_backend="ollama",
    local_privacy_model="phi3",
    fallback_cloud_provider="openai_standard",
    fallback_cloud_model="gpt-4o-mini",
)
```

## Development Install

Editable install:

```bash
pip install -e .[all]
```

Run tests:

```bash
python -m pytest -q
```

## Development Dependencies

Keep the test/lint/build tools in sync:

```bash
pip install -r requirements-dev.txt
```

## Common Setup Mistakes

- using `LMSTUDIO_API_BASE` instead of `LMSTUDIO_BASE_URL`
- using `OLLAMA_API_BASE` instead of `OLLAMA_BASE_URL`
- setting `HF_API_KEY` but not `HUGGINGFACE_API_KEY` for the current `hf_api` backend
- pointing `HF_LOCAL_MODEL` at a repo id instead of a local directory
- pointing `GGUF_MODEL_PATH` at a missing file

## If Setup Fails

Use:

- `llm.diagnostics()`
- `llm.heal(apply=False)`
- [BACKENDS.md](BACKENDS.md)
- [FAQ.md](FAQ.md)
