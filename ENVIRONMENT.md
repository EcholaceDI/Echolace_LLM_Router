# ENVIRONMENT

## Runtime baseline (releasable)
- **OS constraint:** Linux/macOS/WSL2 (Windows supported via PowerShell + venv).
- **Python:** `3.11.9` (project allows `>=3.8`; this is the pinned contributor baseline).
- **pip:** `24.3.1`.

## Install
```bash
cd Echolace-DI-Vault/03_Production_Applications/Echolace_LLM_Router
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip==24.3.1
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Smoke command (production)
```bash
python -c "from llm_router.router import LLMRouter; print('LLM Router import OK')"
```
Expected output:
```text
LLM Router import OK
```
