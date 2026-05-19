# tools/setup_helper.py

"""
Echolace DI – LLM Router Setup Assistant
---------------------------------------

This tool is OPTIONAL and SAFE to run.

It performs NO installations and makes NO system changes.

It simply:
  - Detects which backends are usable
  - Shows which dependencies are missing
  - Suggests install commands (copy/paste)
  - Helps users configure their environment properly
"""

import importlib.util
import shutil
from textwrap import indent


# Mapping of backend → required pip packages
BACKEND_REQUIREMENTS = {
    "OpenAI": ["openai"],
    "OpenAI-Universal": ["requests"],
    "Anthropic": ["anthropic"],
    "Google Gemini": ["google-generativeai"],
    "HuggingFace API": ["huggingface_hub"],
    "HF Local (Transformers)": ["transformers", "torch"],
    "GGUF (llama.cpp)": ["llama_cpp"],
    "GPT4All": ["gpt4all"],
    "Ollama (API mode)": ["requests"],
    "LM Studio (API mode)": ["requests"],
}


def is_installed(pkg: str) -> bool:
    """Returns True if the package is importable."""
    return importlib.util.find_spec(pkg) is not None


def has_uv() -> bool:
    """Returns True if 'uv' is installed on the user's path."""
    return shutil.which("uv") is not None


def run_diagnostics():
    print("\n=== Echolace DI – LLM Router Setup Assistant ===\n")

    results = {}
    uv_available = has_uv()

    # Check each backend for missing dependencies
    for backend, deps in BACKEND_REQUIREMENTS.items():
        missing = [pkg for pkg in deps if not is_installed(pkg)]
        results[backend] = missing

    # Summary block
    print("Dependency Status\n-----------------")
    for backend, missing in results.items():
        if not missing:
            print(f"[READY]   {backend}")
        else:
            print(f"[MISSING] {backend}: {', '.join(missing)}")

    print("\nInstallation Recommendations\n---------------------------")

    # Per-backend suggestions
    for backend, missing in results.items():
        if not missing:
            continue

        print(f"\nBackend: {backend}")
        print("Missing:")

        for pkg in missing:
            print(f"  • {pkg}")

            # pip suggestion
            pip_cmd = f"pip install {pkg}"

            # uv suggestion
            uv_cmd = f"uv pip install --compile {pkg}"

            print(indent("Recommended pip command:", "    "))
            print(indent(pip_cmd, "        "))

            if uv_available:
                print(indent("Optional – faster UV command:", "    "))
                print(indent(uv_cmd, "        "))

    print("\n--------------------------------------------")
    print("Diagnostics complete. No system changes made.")
    print("Install only the dependencies you *choose*.")
    print("--------------------------------------------\n")


if __name__ == "__main__":
    run_diagnostics()
