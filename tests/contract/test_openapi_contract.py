"""The committed OpenAPI contract must match what apps/api.py serves."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_openapi.py"


def _exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_spec_matches_app():
    exporter = _exporter()
    assert exporter.SPEC_PATH.exists(), "run `make openapi`"
    assert exporter.SPEC_PATH.read_text() == exporter.render(), (
        "docs/api/openapi.json drifted from the API; run `make openapi` "
        "and `make ts-client`, then commit the result"
    )


def test_spec_only_exposes_public_surface():
    paths = _exporter().render()
    assert "/internal/hydra" not in paths
    assert '"/api/v1/' in paths
