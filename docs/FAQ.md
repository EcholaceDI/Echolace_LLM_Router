# Frequently Asked Questions

## What is Echolace LLM Router now?

It is a unified LLM interface with a policy layer on top.
The current codebase does more than backend switching:

- privacy-aware routing
- semantic intent classification
- hardware-adaptive local vs cloud decisions
- telemetry and canary benchmarking
- guided healing for broken local setups

## Does the router still support simple usage?

Yes.

```python
from llm_router import LLMInterface

llm = LLMInterface()
print(llm.generate("Explain recursion simply."))
```

The newer policy features are opt-in unless they are part of the default fallback behavior.

## Does it automatically install dependencies?

Not by default.

The router itself does not silently mutate your system.
However, `llm.heal()` can apply specific repair actions if and only if you call it with explicit flags such as:

- `apply=True`
- `allow_network=True`
- `install_python_deps=True`
- `pull_models=True`

Without those flags, it returns a repair plan only.

## What does `privacy_first=True` do?

It enables privacy-aware routing before a request reaches a backend.

That currently means:

- scanning prompt content locally
- detecting PII and secrets
- forcing strict-local execution when policy requires it
- using hybrid-redacted routing when cloud execution is still allowed

If no safe local backend is available for a sensitive request, the router fails closed instead of silently sending the prompt to cloud.

## Does it scan only plain text?

No.

The current privacy layer also scans:

- nested dict payloads
- nested lists and arrays
- chat-style message lists

This happens in the privacy/policy layer before cloud routing decisions are made.

## What is `llm.intent()`?

`llm.intent()` is the public intent-inspection API.
It currently uses semantic retrieval rather than simple keyword matching.

Example:

```python
intent = llm.intent("Refactor this Python function and add tests.")
print(intent["label"])
print(intent["recommended_provider"])
```

The current taxonomy includes:

- `CODE`
- `DEBUGGING`
- `CREATIVE`
- `REASONING`
- `SIMPLE`
- `TRANSLATION`
- `RAG_QA`
- `TOOL_USE_OR_AGENTIC`

## Does the router adapt to hardware state?

Yes.

With hardware-adaptive routing enabled, the policy layer can use:

- CPU pressure
- memory pressure
- GPU pressure
- thermal state
- queue depth
- benchmark history

to decide whether to keep a request local, downgrade to a smaller local route, or offload to cloud.

## Does it benchmark local backends outside live traffic?

Yes.

The telemetry layer now supports canary benchmarks for local runtimes.
It tracks:

- latency
- TTFT
- tokens/sec
- queue depth
- rolling EWMA performance

Optionally, benchmark samples can be persisted to SQLite.

## What does `llm.heal()` support today?

It currently supports meaningful remediation planning for:

- Ollama
- GGUF
- LM Studio
- GPT4All
- Hugging Face local

Examples of generated actions:

- install missing Python packages
- suggest environment variables
- pull missing Ollama models
- discover local GGUF files
- download a GGUF model when `GGUF_MODEL_URL` is configured
- suggest LM Studio or GPT4All model selection
- download a Hugging Face snapshot when `HF_LOCAL_REPO_ID` is configured

## Is `llm.heal()` safe?

It is designed to be explicit and gated.

By default it only reports issues.
When applying actions:

- networked steps require `allow_network=True`
- package installs require `install_python_deps=True`
- model pulls or downloads require `pull_models=True`

Manual actions remain manual.

## Does the router log my prompts?

Not as a persistent product analytics system by default.

What it does keep:

- routing events in diagnostics memory
- privacy planning state for the active request
- benchmark samples if you explicitly enable benchmark persistence

If you need persistent audit logging, that is still future work beyond the current repo.

## What happens if no real backend is available?

The router can fall back to the built-in heuristic backend.
That keeps the interface alive, but it is not a substitute for a real provider or local model.

## Which backend names should I actually use?

Use the real backend ids:

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

Older examples that use names like `openai` or `huggingface` are stale unless they map to one of the above ids in your own wrapper code.

## What license does this repository currently declare?

The canonical license for this project is Apache 2.0 (see `LICENSE`).
The package metadata in `pyproject.toml` is aligned to `Apache-2.0`.

## How do I get a clean environment report?

Use:

```python
llm = LLMInterface()
print(llm.info())
print(llm.diagnostics())
```

If local backends are failing, also run:

```python
print(llm.heal(apply=False))
```

## What should I read next?

- [INSTALL.md](INSTALL.md)
- [BACKENDS.md](BACKENDS.md)
- [STRATEGIC_ROADMAP.md](STRATEGIC_ROADMAP.md)
- [../README.md](../README.md)
