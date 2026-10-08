"""Tests for the log-sanitizing helper.

The value of this helper is entirely in the cases it refuses to let through,
so those get more attention than the happy path.
"""

from __future__ import annotations

from selfmemory.utils.logging import sanitize_for_log


class TestSanitizeForLog:
    def test_passes_through_ordinary_value_unchanged(self):
        assert sanitize_for_log("alice") == "alice"

    def test_escapes_newline_so_it_cannot_forge_a_log_line(self):
        result = sanitize_for_log("alice\nevil forged event")

        assert "\n" not in result
        assert result == "alice\\nevil forged event"

    def test_escapes_carriage_return(self):
        assert "\r" not in sanitize_for_log("alice\revil")

    def test_escapes_crlf_pair_as_two_sequences(self):
        assert sanitize_for_log("a\r\nb") == "a\\r\\nb"

    def test_coerces_non_string_rather_than_raising(self):
        assert sanitize_for_log(1234) == "1234"
        assert sanitize_for_log(None) == "None"

    def test_preserves_value_rather_than_stripping_it(self):
        """Escaping keeps the evidence; deleting the newline would hide it.

        A stripping implementation would yield "evidence" here, silently
        joining two fields. The escaped form shows a newline was present.
        """
        assert sanitize_for_log("evid\nence") == "evid\\nence"
        assert sanitize_for_log("evid\nence") != "evidence"
