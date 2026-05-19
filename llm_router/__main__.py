from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from .diagnostics import json_report, pretty_print, scan


def _cmd_diagnose(args: argparse.Namespace) -> int:
    if args.json:
        sys.stdout.write(json_report())
        sys.stdout.write("\n")
        return 0
    pretty_print()
    return 0


def _cmd_env(args: argparse.Namespace) -> int:
    report: Dict[str, Any] = scan()
    sys.stdout.write(
        json.dumps(report.get("environment", {}), indent=2, ensure_ascii=False)
    )
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m llm_router", description="Echolace LLM Router CLI"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    diagnose = sub.add_parser(
        "diagnose", help="Print diagnostics (human-readable by default)"
    )
    diagnose.add_argument("--json", action="store_true", help="Output JSON report")
    diagnose.set_defaults(func=_cmd_diagnose)

    env = sub.add_parser("env", help="Print environment summary from diagnostics")
    env.set_defaults(func=_cmd_env)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
