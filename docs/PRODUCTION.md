# Production Guide

This guide focuses on practical production deployment patterns for embedding `LLMInterface` in services.

## Pattern: FastAPI/Flask embedding (singleton)

Create a single `LLMInterface` instance at process startup and reuse it for requests.
This keeps:
- telemetry/hardware monitor state warm
- policy engine and routing events consistent

### FastAPI example (minimal)

```python
from fastapi import FastAPI, HTTPException
from llm_router import LLMInterface

app = FastAPI()

llm = LLMInterface(
    privacy_first=True,
    intent_routing=True,
    hardware_adaptive=True,
    start_hardware_monitor=True,
)

@app.post("/generate")
def generate(payload: dict):
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")
    try:
        text = llm.generate(prompt)
        return {"text": text, "routing_plan": llm.routing_plan()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
```

### Flask example (minimal)

```python
from flask import Flask, jsonify, request
from llm_router import LLMInterface

app = Flask(__name__)
llm = LLMInterface(privacy_first=True)

@app.post("/generate")
def generate():
    data = request.get_json(force=True)
    text = llm.generate(data["prompt"])
    return jsonify({"text": text, "routing_plan": llm.routing_plan()})
```

## Pattern: REST API wrapper (reference implementation)

The FastAPI snippet above is the recommended “thin wrapper” approach:
- accept input
- call `llm.generate()`
- return `routing_plan` for auditability (or log it server-side)

## Configuration best practices

- Use a secret manager (Vault, AWS Secrets Manager, GitHub Environments, etc.) for API keys.
- Prefer environment variables (the backends already read from env vars).
- Decide provider priority intentionally:
  - use `provider=...` to force a provider
  - or leave it unset and rely on policy-driven planning

## Error handling patterns

### When all backends fail

Treat `LLMBackendError`/backend exceptions as upstream dependency failures.
Recommended behavior:
- return 502/503 to callers
- log routing plan + selected backend + failure reason
- surface a stable request identifier if you implement request IDs (recommended for support)

### Timeouts and retries

Backends may have different timeout semantics.
Recommended strategy:
- apply timeouts at the HTTP client or request boundary
- retry only on clearly transient errors (429, 5xx) and only for idempotent requests

## Observability hooks

- Structured logging:
  - set `ECHOLACE_LOG_FORMAT=json` and `ECHOLACE_LOG_LEVEL=INFO`
- Collect diagnostics:
  - `python -m llm_router diagnose --json`

For OpenTelemetry/Prometheus integration, use logs + `routing_plan()` + `routing_events()` as the initial audit trail.

