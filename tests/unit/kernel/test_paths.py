"""Tests for confining configured paths to a directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from selfmemory.kernel.paths import resolve_within

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "data"


def test_a_relative_file_resolves_inside_base(base):
    assert resolve_within(base, "knowledge.db") == base / "knowledge.db"


def test_a_nested_relative_path_resolves_inside_base(base):
    assert resolve_within(base, "stores/kb.db") == base / "stores" / "kb.db"


def test_a_harmless_dot_dot_that_stays_inside_is_allowed(base):
    assert resolve_within(base, "a/../kb.db") == base / "kb.db"


def test_an_absolute_path_inside_base_is_allowed(base):
    inside = base / "kb.db"
    assert resolve_within(base, str(inside)) == inside


@pytest.mark.parametrize(
    "configured",
    [
        "../escape.db",
        "../../etc/kb.db",
        "a/../../escape.db",
        "/etc/kb.db",
        "/tmp/elsewhere.db",
    ],
)
def test_paths_escaping_base_are_refused(base, configured):
    with pytest.raises(ValueError, match="must resolve inside"):
        resolve_within(base, configured)


def test_a_sibling_sharing_the_prefix_is_refused(tmp_path):
    """ "/srv/data-evil" starts with "/srv/data" as a string; it is not inside it."""
    base = tmp_path / "data"
    with pytest.raises(ValueError):
        resolve_within(base, str(tmp_path / "data-evil" / "kb.db"))


@pytest.mark.parametrize("configured", ["", ".", "a/.."])
def test_the_base_itself_is_refused(base, configured):
    """A database file cannot be the directory it is supposed to live in."""
    with pytest.raises(ValueError):
        resolve_within(base, configured)


def test_the_error_does_not_echo_raw_control_characters(base):
    with pytest.raises(ValueError) as exc:
        resolve_within(base, "/etc/x\nforged line")
    assert "\n" not in str(exc.value)


def test_resolution_does_not_touch_the_filesystem(base):
    resolve_within(base, "not/created/yet.db")
    assert not base.exists()
