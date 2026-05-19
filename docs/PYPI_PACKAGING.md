# PyPI Packaging (`echolace-llm-router`)

This project is already structured as a modern Python package via `pyproject.toml` and `setuptools`.

## Build locally

From `03_Production_Applications/Echolace_LLM_Router`:

- `python -m pip install -r requirements-dev.txt`
- `python -m pip install -e .`
- `python -m build`

Artifacts are written to `dist/`.

## Publish (manual)

Recommended approach is to publish from CI with a protected environment, but for a manual publish:

- `python -m pip install twine`
- `python -m twine check dist/*`
- `python -m twine upload dist/*`

## Versioning

Version lives in `pyproject.toml` under `[project].version`.

## What CI does today

The workflow `.github/workflows/llm-router-release-verify.yml`:
- runs formatting checks, linting, tests
- runs `python -m build`
- runs `pip-audit` (best-effort)
- uploads `dist/` and `release-evidence/<version>/` as workflow artifacts

