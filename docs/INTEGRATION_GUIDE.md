# Integration Guide

This guide is for integrating `llm_router.LLMInterface` into an application or agent.
It focuses on common setups and the operational knobs that tend to matter in practice.

## Install

From the project root:

- Minimal (core interface + HTTP):
  - `pip install -e .`
- Development (tests + build tooling):
  - `pip install -r requirements-dev.txt`

Optional feature sets (examples):

- `pip install -e .[openai]`
- `pip install -e .[anthropic]`
- `pip install -e .[google]`
- `pip install -e .[huggingface]`
- `pip install -e .[privacy]`
- `pip install -e .[intent]`
- `pip install -e .[telemetry]`
- `pip install -e .[local]`
- `pip install -e .[all]`

## Quick Start (basic generate)

```python
from llm_router import LLMInterface

llm = LLMInterface()
print(llm.generate("In one sentence: what is an LLM router?"))
```

If no backend credentials are configured, `available_backends()` may be empty or generation will fail. In that case, configure a backend (see below).

## Configure backends (environment variables)

Cloud backends:

- OpenAI:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL` (default: `gpt-4o-mini`)
- Azure OpenAI:
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_DEPLOYMENT`
- Anthropic:
  - `ANTHROPIC_API_KEY`
  - `ANTHROPIC_MODEL` (default is set in the backend implementation)
- Google Gemini:
  - `GOOGLE_API_KEY`
  - `GOOGLE_MODEL`
- HuggingFace API:
  - `HUGGINGFACE_API_KEY`
  - `HF_API_MODEL`
- Universal OpenAI-compatible endpoints (vLLM / other providers):
  - `UNIVERSAL_OPENAI_BASE_URL`
  - `UNIVERSAL_OPENAI_API_KEY`
  - `UNIVERSAL_OPENAI_MODEL`

Local backends (paths / model locations):

- HF Local:
  - `HF_LOCAL_MODEL` (path or identifier; see `llm_router/providers/hf_local_backend.py`)
- HF Image Local:
  - `HF_IMAGE_MODEL`

Model storage helpers (used by path helpers and some local flows):

- `ECHOLACE_MODELS_DIR` (root directory for local models)
- `ECHOLACE_GGUF_DIR`
- `ECHOLACE_HF_DIR`

## Common use cases

### 1) “Always use a specific provider”

```python
from llm_router import LLMInterface

llm = LLMInterface(provider="openai_standard", model="gpt-4o-mini")
print(llm.generate("Hello."))
```

At runtime, you can also switch:

```python
llm.switch("anthropic")
```

### 2) Privacy-first routing

Use this when you want structured PII/secret scanning before cloud routing.

```python
from llm_router import LLMInterface

llm = LLMInterface(
    privacy_first=True,
    privacy_profile="default",
    local_privacy_backend="ollama",
    fallback_cloud_provider="openai_standard",
)
```

High-value calls:

- `llm.scan(payload)` → structured scan result
- `llm.routing_plan(payload)` → route decision + redaction plan

Runnable demo: `examples/privacy_first_routing.py`.

### 3) Semantic intent routing / classification

Use this when prompts should be routed by “task intent” (e.g., CODE vs TRANSLATION vs RAG_QA).

```python
from llm_router import LLMInterface

llm = LLMInterface(intent_routing=True)
print(llm.intent("Write unit tests for this function.", top_k=3, include_route=True))
```

Runnable demo: `examples/semantic_intent_classification.py`.

### 4) Hardware-adaptive routing

Use this when local vs cloud choices should consider current machine capability and telemetry.

```python
from llm_router import LLMInterface

llm = LLMInterface(hardware_adaptive=True, start_hardware_monitor=True)
print(llm.hardware_status())
```

Runnable demo: `examples/hardware_adaptive_routing.py`.

### 5) Healing / guided remediation

Use this when you want the router to propose (or apply) remediation steps for broken local runtimes.

```python
plan = llm.heal(apply=False, allow_network=False, install_python_deps=False, pull_models=False)
print(plan["plan"])
```

## Operational tips

- Prefer `python -m pytest -q` over `pytest` when PATH tooling isn’t installed globally.
- If your deployment environment is locked down, keep `llm.heal(apply=False)` and apply fixes via standard infra workflows.

