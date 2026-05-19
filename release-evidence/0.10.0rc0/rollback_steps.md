# Rollback Test Steps (Prior Tag Reinstall/Checkout)

> Status: Blocked in this repository snapshot because no Git tags are present locally (`git tag --list` returned empty).

## Intended rollback validation flow

1. Identify prior release tag:
   ```bash
   git fetch --tags
   git tag --list 'v*' | sort -V | tail -n 5
   ```
2. Checkout prior tag in detached HEAD:
   ```bash
   git checkout <prior_tag>
   ```
3. Reinstall package from prior tag source:
   ```bash
   python -m pip install --force-reinstall .
   ```
4. Run smoke validation:
   ```bash
   pytest -q
   ```
5. Return to release branch:
   ```bash
   git checkout release/llm-router-rc0
   ```

## Current outcome

- Prior-tag rollback test could not be executed because no baseline tag exists in the local clone.
