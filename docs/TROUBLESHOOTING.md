# Troubleshooting

This guide documents common error scenarios for the Echolace LLM Router and how to resolve them.

## “No real backends available”

Symptoms:
- `llm.available_backends()` returns `[]`
- example scripts refuse to run because no backend is available

Causes:
- No provider credentials configured (cloud backends)
- Optional dependencies not installed for the backend you want

Fix:
- Configure at least one provider:
  - OpenAI: set `OPENAI_API_KEY`
  - Anthropic: set `ANTHROPIC_API_KEY`
  - Gemini: set `GOOGLE_API_KEY`
- Install extras as needed:
  - `pip install -e .[openai]` / `.[anthropic]` / `.[google]` / `.[all]`

## “Privacy policy requires strict local execution, but no local backend is currently available.”

Where it comes from:
- Raised by `LLMInterface.generate()` after policy planning when `RoutePlan.provider == "blocked"`.

Causes:
- `privacy_first=True` and the prompt contains regulated entities (e.g. HIPAA profile), but no local backend is available.

Fix:
- Install / configure a local backend (e.g. Ollama) and ensure it is discoverable:
  - `pip install -e .[local]` (if required by the backend)
  - ensure the runtime is installed (Ollama/LM Studio/etc.)
- Or relax privacy policy if acceptable for your environment:
  - use `privacy_profile="default"` instead of `hipaa`, or disable privacy-first routing.

## Backend credential errors

Examples:
- `OPENAI_API_KEY not set...`
- `GOOGLE_API_KEY is not set...`
- `Neither OPENAI_API_KEY nor Azure OpenAI credentials are set.`

Fix:
- Ensure the corresponding env vars are configured in your runtime (local shell, container, or orchestration layer).
- Prefer secret managers for production deployments.

## Dependency missing errors

Symptoms:
- `Missing dependency: <package>` (raised by some backends)

Fix:
- Install the correct optional dependency group:
  - e.g. `pip install -e .[openai]` or `pip install -e .[all]`

## Structured logging

The router supports structured logging via environment variables:

- `ECHOLACE_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`
- `ECHOLACE_LOG_FORMAT=json|text`

In JSON mode, logs include an `event` field plus structured metadata for routing decisions.

