# Supported Backends

This document reflects the current backend implementations in the repository.
Provider ids listed here match the names used by `LLMInterface(provider=...)` and by diagnostics output.

## Backend Ids

The router currently registers these backends:

- `anthropic`
- `gguf`
- `google`
- `gpt4all`
- `hf_api`
- `hf_local`
- `lmstudio`
- `ollama`
- `openai_standard`
- `openai_streaming`
- `openai_universal`

## Capability Summary

| Backend id | Local | Streaming | Model source | Main env vars |
|---|---:|---:|---|---|
| `anthropic` | No | Yes | Anthropic API | `ANTHROPIC_API_KEY` |
| `openai_standard` | No | No | OpenAI or Azure OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, `AZURE_OPENAI_*` |
| `openai_streaming` | No | Yes | OpenAI API | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `openai_universal` | No | Yes | Any OpenAI-compatible endpoint | `UNIVERSAL_OPENAI_BASE_URL`, `UNIVERSAL_OPENAI_API_KEY`, `UNIVERSAL_OPENAI_MODEL` |
| `google` | No | Yes | Google Gemini API | `GOOGLE_API_KEY`, `GOOGLE_MODEL` |
| `hf_api` | No | Yes | Hugging Face Inference API | `HUGGINGFACE_API_KEY`, `HF_API_MODEL` |
| `hf_local` | Yes | Yes | Local Transformers model directory | `HF_LOCAL_MODEL` |
| `gguf` | Yes | Yes | Local `.gguf` file via llama.cpp | `GGUF_MODEL_PATH` |
| `gpt4all` | Yes | Yes | GPT4All local server | `GPT4ALL_BASE_URL`, `GPT4ALL_MODEL` |
| `lmstudio` | Yes | Yes | LM Studio local OpenAI-compatible server | `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` |
| `ollama` | Yes | Yes | Ollama local server | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

## Cloud Backends

### `anthropic`

Purpose:
- Claude family routing, including code and writing workloads

Requirements:
- `anthropic` package
- `ANTHROPIC_API_KEY`

Notes:
- Exposed as a cloud backend in route planning
- Common intent target for `CODE`, `DEBUGGING`, and `CREATIVE`

### `openai_standard`

Purpose:
- non-streaming OpenAI and Azure OpenAI calls

Requirements:
- `openai` package
- one of:
  - `OPENAI_API_KEY`
  - Azure configuration: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`

Notes:
- `generate()` only
- used heavily as a cloud fallback target
- default model comes from `OPENAI_MODEL` or router fallback config

### `openai_streaming`

Purpose:
- OpenAI streaming backend with normalized chunk output

Requirements:
- `openai` package
- `OPENAI_API_KEY`

Notes:
- implements true provider streaming
- useful when low-latency partial output matters more than fallback simplicity

### `openai_universal`

Purpose:
- connect to any OpenAI-compatible endpoint

Requirements:
- `requests`
- `UNIVERSAL_OPENAI_BASE_URL`
- optional `UNIVERSAL_OPENAI_API_KEY`
- optional `UNIVERSAL_OPENAI_MODEL`

Notes:
- the base URL should point to an OpenAI-compatible `/v1` API
- useful for self-hosted or third-party compatible runtimes

### `google`

Purpose:
- Google Gemini backend

Requirements:
- `google-generativeai`
- `GOOGLE_API_KEY`

Notes:
- streaming supported
- default model comes from `GOOGLE_MODEL` or the provider default

### `hf_api`

Purpose:
- Hugging Face hosted inference

Requirements:
- `huggingface_hub`
- `HUGGINGFACE_API_KEY`

Notes:
- default model comes from `HF_API_MODEL`
- `generate()` uses streaming when possible and falls back to non-streaming text generation

## Local Backends

### `hf_local`

Purpose:
- local Transformers inference

Requirements:
- `transformers`
- `torch`
- `HF_LOCAL_MODEL` pointing to a local model directory

Notes:
- the configured directory must exist locally
- the healing planner can discover local model directories with `config.json`
- this backend participates in privacy-first and hardware-adaptive routing

### `gguf`

Purpose:
- local `.gguf` inference through `llama-cpp-python`

Requirements:
- `llama-cpp-python`
- `GGUF_MODEL_PATH`

Notes:
- the model path must point to an existing `.gguf` file
- the healing planner can:
  - discover local `.gguf` files
  - suggest `GGUF_MODEL_PATH`
  - build a download workflow when `GGUF_MODEL_URL` is configured

### `gpt4all`

Purpose:
- GPT4All local server routing

Requirements:
- reachable GPT4All server
- optional `GPT4ALL_BASE_URL`
- optional `GPT4ALL_MODEL`

Notes:
- the backend talks to a local HTTP server, not the Python `gpt4all` runtime directly
- healing can suggest starting the server and setting a default model
- discovered GGUF files can be suggested as GPT4All model inputs

### `lmstudio`

Purpose:
- LM Studio local OpenAI-compatible server routing

Requirements:
- reachable LM Studio server
- optional `LMSTUDIO_BASE_URL`
- optional `LMSTUDIO_MODEL`

Notes:
- LM Studio must be opened manually
- a model must be loaded in the UI
- the OpenAI-compatible local server must be enabled in LM Studio
- healing surfaces these steps explicitly

### `ollama`

Purpose:
- Ollama local server routing

Requirements:
- reachable Ollama server
- optional `OLLAMA_BASE_URL`
- optional `OLLAMA_MODEL`

Notes:
- healing can suggest:
  - starting `ollama serve`
  - pulling a missing model
  - setting a default model from discovered runtime models

## How Backends Interact With The Policy Layer

The provider modules are execution endpoints.
Policy decisions happen above them.

Examples:

- privacy-first routing can force a sensitive request from a cloud backend to a local backend
- semantic intent routing can change the selected cloud backend even when the user did not specify one
- hardware-adaptive routing can downgrade a request from one local backend to a smaller local backend or to cloud

## Healing Coverage By Backend

`llm.heal()` currently supports meaningful remediation for:

- `ollama`
- `gguf`
- `lmstudio`
- `gpt4all`
- `hf_local`

Cloud backends mainly receive dependency and environment-variable guidance.

## Diagnostics Expectations

Every backend is expected to provide:

- `.available()`
- `.diagnose()`
- `.generate(prompt, **kwargs)`
- optional `.stream(prompt, **kwargs)`

The diagnostics and healing layers rely on those reports.
If you add a new backend, make sure `diagnose()` exposes enough information for safe remediation planning.
