# Echolace LLM Router release-candidate automation

.PHONY: lint test build release-verify

lint:
	python -m compileall llm_router tests
	python -m flake8 llm_router tests

test:
	pytest

build:
	python -m build

release-verify: lint test build
	@echo "Release verification complete. Evidence should be stored in release-evidence/<version>/."
