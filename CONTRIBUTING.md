# Contributing

Thanks for helping improve the Echolace LLM Router.
This project is routing infrastructure; changes should preserve correctness, privacy guarantees, and auditability.

## Quick start

From `03_Production_Applications/Echolace_LLM_Router`:

1. Create a virtualenv and install dependencies:
   - `python -m venv .venv`
   - activate it
   - `python -m pip install --upgrade pip`
   - `python -m pip install -r requirements-dev.txt`
   - `python -m pip install -e .`
2. Run checks:
   - `python -m black --check .`
   - `python -m isort --check-only .`
   - `python -m flake8 llm_router tests examples`
   - `python -m pytest -q`

## What to change (and what not to)

High-value contributions:
- New backends (cloud or local) with clear env var config and diagnostics.
- Improvements to `RequestPolicyEngine` and `RoutePlanner` that add determinism and audit metadata.
- Privacy scanning improvements (structured payload handling, profile tuning).
- Intent classification enhancements (schemas, retrieval, route regret tracking).
- Tests for routing decisions and policy invariants.

Avoid:
- Adding provider credentials or secrets to the repo.
- Making behavior non-deterministic in tests.
- Tight coupling to a single vendor where a generic interface is possible.

## Code style

- Formatting: `black`
- Import ordering: `isort` (configured via `pyproject.toml`)
- Linting: `flake8` (configured via `.flake8`)

## Tests

We expect:
- unit tests for policy/routing logic
- integration-style tests using stub backends (no real credentials required)
- end-to-end tests that verify privacy redaction + rehydration semantics

Run:
- `python -m pytest -q`

## Release evidence (when relevant)

When a change affects routing behavior, privacy posture, or backend selection logic, attach evidence:

- `release-evidence/<version>/test-and-lint.log`
- `release-evidence/<version>/build.log`
- `release-evidence/<version>/pip-audit.log`

CI workflow support:
- `.github/workflows/llm-router-release-verify.yml`

## Pull request checklist

- [ ] Tests added/updated for behavior changes
- [ ] `black`, `isort`, `flake8`, and `pytest` pass
- [ ] Docs updated if the public behavior or configuration changed
- [ ] No secrets committed

