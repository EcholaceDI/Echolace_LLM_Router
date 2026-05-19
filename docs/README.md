# Documentation

This documentation set now reflects the current router implementation, not just the original multi-backend interface.
Echolace LLM Router currently ships a policy-driven routing layer with privacy controls, semantic intent routing, hardware-adaptive telemetry, and guided healing.

## Start Here

- [Installation](INSTALL.md)
- [Backend Notes](BACKENDS.md)
- [FAQ](FAQ.md)
- [Changelog](../CHANGELOG.md)
- [Integration Guide](INTEGRATION_GUIDE.md)
- [Deployment](DEPLOYMENT.md)
- [Project Metadata](PROJECT_METADATA.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [PyPI Packaging](PYPI_PACKAGING.md)
- [Strategic Roadmap](STRATEGIC_ROADMAP.md)

## Current Feature Set

### Core router

- single `LLMInterface` surface for cloud and local backends
- automatic backend selection with manual override support
- normalized `generate()` and `stream()` behavior
- runtime switching via `switch()` and `use_backend()`

### Privacy-aware routing

- `privacy_first=True` support on `LLMInterface`
- local PII and secret scanning before cloud routing
- strict-local and hybrid-redacted execution modes
- structured payload scanning for nested dicts, lists, and chat-style message payloads
- privacy profiles such as `default`, `hipaa`, `gdpr`, `pci`, and `soc2`

### Semantic intent routing

- `llm.intent()` public API
- semantic retrieval-based intent classification
- expanded taxonomy:
  - `CODE`
  - `DEBUGGING`
  - `CREATIVE`
  - `REASONING`
  - `SIMPLE`
  - `TRANSLATION`
  - `RAG_QA`
  - `TOOL_USE_OR_AGENTIC`
- tenant-specific intent schemas
- route-regret tracking

### Hardware-adaptive telemetry

- `llm.hardware_status()` public API
- background hardware monitoring
- canary benchmarks for local backends
- rolling latency, TTFT, queue depth, and tokens/sec metrics
- optional SQLite persistence in the benchmark store
- downgrade recommendations for local routing

### Healing and diagnostics

- `llm.diagnostics()` and `llm.heal()`
- backend availability and environment reporting
- repair-plan generation for missing packages, models, and runtime configuration
- Ollama, GGUF, LM Studio, GPT4All, and Hugging Face local remediation guidance
- safer apply behavior with retry-aware command execution and explicit network gating

## Public API Surface

The current `LLMInterface` constructor supports:

```python
LLMInterface(
    provider=None,
    model=None,
    privacy_first=False,
    hardware_adaptive=False,
    intent_routing=False,
    local_privacy_backend="ollama",
    local_privacy_model=None,
    fallback_cloud_provider="openai_standard",
    fallback_cloud_model="gpt-4o-mini",
    privacy_profile="default",
    intent_schema=None,
    policy_engine=None,
    start_hardware_monitor=False,
    hardware_monitor_interval=5,
    **kwargs,
)
```

High-value methods:

- `generate(prompt, **kwargs)`
- `stream(prompt, **kwargs)`
- `intent(prompt, top_k=3, include_route=True, schema_name=None)`
- `heal(apply=False, allow_network=False, install_python_deps=False, pull_models=False, prefer_local=True, backend=None)`
- `diagnostics()`
- `hardware_status()`
- `privacy_status()`
- `routing_plan()`
- `routing_events()`

## Recommended Reading Order

If you are new to the project:

1. Read [Installation](INSTALL.md).
2. Read [Backend Notes](BACKENDS.md).
3. Read [Strategic Roadmap](STRATEGIC_ROADMAP.md), especially the implementation-status section.

If you are integrating the router into an application:

1. Start with the root [README](../README.md).
2. Review [FAQ](FAQ.md).
3. Use `llm.diagnostics()` and `llm.heal()` early in setup.

If you are continuing development:

1. Review [Strategic Roadmap](STRATEGIC_ROADMAP.md).
2. Inspect `llm_router/policies/`, `llm_router/security/`, `llm_router/telemetry/`, and `llm_router/healing/`.
3. Run `python -m pytest -q` before and after changes.
