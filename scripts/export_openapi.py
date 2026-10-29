"""Dump the /api/v1 OpenAPI contract to docs/api/openapi.json.

Usage: uv run python scripts/export_openapi.py [--check]
"""

import json
import sys
from pathlib import Path

PUBLIC_PREFIXES = ("/api/v1/", "/health")
SPEC_PATH = Path(__file__).resolve().parents[1] / "docs" / "api" / "openapi.json"


def render() -> str:
    from selfmemory.apps.api import app

    spec = dict(app.openapi())
    # The public contract is /api/v1 plus health; internal Hydra hooks and
    # discovery documents are not part of the client surface.
    spec["paths"] = {
        path: item
        for path, item in spec["paths"].items()
        if path.startswith(PUBLIC_PREFIXES)
    }
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


def main() -> int:
    spec = render()
    if "--check" in sys.argv:
        if not SPEC_PATH.exists() or SPEC_PATH.read_text() != spec:
            print(f"{SPEC_PATH} is stale; run `make openapi`", file=sys.stderr)
            return 1
        return 0
    SPEC_PATH.write_text(spec)
    print(f"wrote {SPEC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
