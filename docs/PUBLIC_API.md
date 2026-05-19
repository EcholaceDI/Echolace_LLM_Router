# Public API Surface

This document describes the **public, supported API surface** of the router.

The stable API is intentionally small:
- `llm_router.LLMInterface` is the main entrypoint.
- Everything else should be treated as internal unless explicitly documented here.

## `LLMInterface`

Import:

```python
from llm_router import LLMInterface
```

Constructor (common knobs):

- `provider: str | None` — provider override (forces a backend)
- `model: str | None` — model override
- `privacy_first: bool` — enable privacy-aware routing
- `privacy_profile: str` — `default`, `hipaa`, `gdpr`, `pci`, `soc2`
- `intent_routing: bool` — enable intent classification + routing
- `intent_schema: str | None` — tenant schema name (optional)
- `hardware_adaptive: bool` — enable hardware-aware routing signals
- `start_hardware_monitor: bool` — start background sampling (optional)
- `hardware_monitor_interval: int` — sampling interval seconds

### Generation

- `generate(prompt, **kwargs) -> str`
  - `prompt` can be text or a structured payload (privacy scanning supports nested objects and message-list structures).
- `stream(prompt, **kwargs) -> Iterator[dict]`
  - yields token chunks (shape is backend-dependent)

### Routing / diagnostics

- `diagnostics() -> dict`
- `routing_plan() -> dict | None`
- `routing_events() -> list[dict]`
- `available_backends() -> list[str]`
- `best_backend() -> str | None`
- `current_backend() -> str`
- `info() -> dict`

### Privacy

- `scan(payload) -> dict`
  - returns privacy scan results
- `privacy_status() -> dict | None`

### Intent

- `intent(prompt: str, top_k: int = 3, include_route: bool = True, schema_name: str | None = None) -> dict`

### Healing

- `heal(apply: bool = False, ...) -> dict`

### Backend switching

- `switch(provider: str, model: str | None = None) -> bool`
- `use_backend(provider: str, model: str | None = None)` (context manager)

## CLI (supported)

- `python -m llm_router diagnose [--json]`
- `python -m llm_router env`

If installed as a package, a console script is also provided:
- `echolace-diagnose`

