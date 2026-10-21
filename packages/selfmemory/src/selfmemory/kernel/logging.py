"""Helpers for writing values into logs safely.

A log line is a trust boundary. Anything interpolated into one should be
treated as attacker-controlled, because log output is routinely shipped to
aggregators, terminals and dashboards that re-interpret it.

The specific hazard is a value carrying a newline. A newline in an
attacker-supplied string lets them terminate the line you wrote and forge the
next one, so a log reader sees a fabricated "successful login" event that your
code never emitted.

This lives in the SDK rather than in ``server`` because the values needing it
show up in both layers, and ``server`` already depends on ``selfmemory``.
Inverting that would make the published package import the web app.
"""

from __future__ import annotations

__all__ = ["sanitize_for_log"]


def sanitize_for_log(value: object) -> str:
    """Return ``value`` as a string with newlines escaped, safe to interpolate.

    Backslash-escapes rather than strips: removing the newline would silently
    join two fields into one and hide that the input was malformed.

    Args:
        value: Any value about to be written to a log. Non-strings are
            coerced with ``str()`` so callers need not branch on type.

    Returns:
        str: The value with ``\\n`` and ``\\r`` replaced by their literal
        escape sequences.

    Examples:
        >>> sanitize_for_log("alice")
        'alice'
        >>> sanitize_for_log("alice\\nevil forged event")
        'alice\\\\nevil forged event'
    """
    return str(value).replace("\n", "\\n").replace("\r", "\\r")
