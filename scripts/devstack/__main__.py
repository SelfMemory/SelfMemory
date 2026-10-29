"""CLI entry point: ``python -m scripts.devstack <command>``.

Error handling lives here so the orchestration modules can raise plain
exceptions with an accurate message and let one place decide how to present
it. Every failure mode gets a non-zero exit code, which is what a Makefile or
CI step needs in order to stop rather than carry on.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys

from devstack import lifecycle
from scripts.devstack.settings import ConfigError, load_settings
from scripts.devstack.waiters import ProbeError

# Failures that are the operator's to fix, not bugs. Printed without a
# traceback, because a stack trace implies something is broken in the code
# when really the code is reporting a missing service.
ACTIONABLE = (
    ConfigError,
    lifecycle.PreflightError,
    ProbeError,
    TimeoutError,
    RuntimeError,
    OSError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devstack",
        description="Bring up the SelfMemory local development stack.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser(
        "up",
        help="start Mongo and the API (the wiki is on disk; the agent runs per job)",
    )
    up_parser.add_argument(
        "--no-reload",
        action="store_true",
        help="disable uvicorn auto-reload",
    )

    down_parser = subparsers.add_parser("down", help="stop the containers")
    down_parser.add_argument(
        "--volumes",
        action="store_true",
        help="also delete Mongo volumes (tenancy, run queue); the wiki data root "
        "on disk is never touched",
    )

    subparsers.add_parser(
        "status", help="report Mongo, API, wiki data root, agent and isolation"
    )
    subparsers.add_parser("check", help="run preflight checks and change nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()

    if args.command == "status":
        return lifecycle.status(settings)

    if args.command == "check":
        lifecycle.check_tools(settings)
        lifecycle.check_config(settings)
        print("[devstack] preflight OK")
        return 0

    if args.command == "down":
        return lifecycle.down(settings, volumes=args.volumes)

    if args.no_reload:
        settings = dataclasses.replace(settings, api_reload=False)

    return lifecycle.up(settings)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ACTIONABLE as exc:
        print(f"\n[devstack] {type(exc).__name__}: {exc}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
