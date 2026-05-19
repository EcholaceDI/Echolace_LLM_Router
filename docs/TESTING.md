# Testing Matrix

All tests run headless using `pytest` and share the same development dependencies tracked in `requirements-dev.txt`.

## Unit Tests

| Suite | Description | Command |
|-------|-------------|---------|
| `tests/test_healing_planner.py` | Validates healing workflows, environment hints, discovery of GGUF/HF models, and retryable actions. | `python -m pytest tests/test_healing_planner.py` |
| `tests/test_paths.py` | Guarantees the new universal path helpers respect environment overrides on Windows and POSIX-style inputs. | `python -m pytest tests/test_paths.py` |
| `tests/*` | `test_routing_policies.py`, `test_privacy_handling.py`, `test_intent_pipeline.py`, `test_hardware_benchmarking.py` and others exercise policy, privacy, intent, and telemetry code paths. | `python -m pytest tests` |

## Linting

- `python -m flake8 llm_router/paths.py llm_router/healing/planner.py tests/test_paths.py tests/test_healing_planner.py` (requires `flake8` from `requirements-dev.txt`)

## Build Verification

- `python -m build` ensures setuptools packaging succeeds and wheel/source artifacts can be produced.

## CI Nominal Flow

1. `pip install -r requirements-dev.txt`
2. `python -m flake8 llm_router/paths.py llm_router/healing/planner.py tests/test_paths.py tests/test_healing_planner.py`
3. `python -m pytest tests`
4. `python -m build`

Document any failures in `docs/RUNBOOK.md` and rerun the relevant command until green.
