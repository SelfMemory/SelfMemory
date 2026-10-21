"""Readiness probes for the local stack.

Separate from orchestration because waiting is where a startup script usually
goes wrong. ``time.sleep`` after a spawn assumes a startup time nobody
measured; polling a real endpoint either succeeds or fails, and fails loudly
on timeout.

Each function returns ``True`` on success and raises ``TimeoutError`` with the
last observed state on failure. Raising beats returning ``False`` here: every
caller's next action is to give up and explain, so there is no branch that
silently continues.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

# Long enough for a cold container start on a laptop, short enough that a
# genuinely broken service surfaces in under three minutes.
DEFAULT_POLL_INTERVAL = 1.0


class ProbeError(RuntimeError):
    """A probe could not reach or interpret its target."""


def wait_for_port(
    host: str,
    port: int,
    timeout: float,
    *,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    label: str | None = None,
) -> bool:
    """Block until ``host:port`` accepts a TCP connection.

    A TCP accept is the right bar for Mongo: its listening socket appears once
    it is serving, and it holds the port during index builds anyway.

    Raises:
        TimeoutError: The port never opened within ``timeout`` seconds.
    """
    name = label or f"{host}:{port}"
    deadline = time.monotonic() + timeout
    last_error: str = "no connection attempt completed"

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=poll_interval + 2):
                return True
        except OSError as exc:
            last_error = str(exc)
        time.sleep(poll_interval)

    raise TimeoutError(
        f"{name} did not accept connections within {timeout:.0f}s. "
        f"Last error: {last_error}"
    )


def wait_for_http(
    url: str,
    timeout: float,
    *,
    expect_status: int = 200,
    expect_json_keys: tuple[str, ...] = (),
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    label: str | None = None,
) -> bool:
    """Block until ``url`` returns ``expect_status`` and, optionally, a matching body.

    ``expect_json_keys`` is an identity check, not decoration. A status code
    alone will happily be satisfied by whatever else happens to hold the port:
    on a developer machine something unrelated answering 200 on :8081 would
    otherwise be reported as a healthy SelfMemory API, and the real server
    would never be noticed as missing. Requiring the payload to contain the
    keys this service actually returns means "ready" means *this* service is
    ready.

    Raises:
        TimeoutError: The endpoint answered with another status, returned a
            body without the expected keys, or stopped answering, within
            ``timeout`` seconds. The last observation is included, because
            "503" alone does not say which dependency is unhappy.
    """
    name = label or url
    deadline = time.monotonic() + timeout
    last_seen = "no response received"

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=poll_interval + 2) as response:
                if response.status != expect_status:
                    last_seen = f"HTTP {response.status}"
                else:
                    missing = _missing_json_keys(response.read(), expect_json_keys)
                    if not missing:
                        return True
                    last_seen = (
                        f"HTTP {response.status} but body is missing "
                        f"{', '.join(missing)} -- something other than the "
                        f"expected service is answering on this port"
                    )
        except urllib.error.HTTPError as exc:
            # A 503 from /health is a real answer: the API is up and telling us
            # a dependency is not. Record the body, keep polling.
            last_seen = f"HTTP {exc.code} {_read_body(exc)}"
        except (urllib.error.URLError, OSError) as exc:
            last_seen = f"unreachable ({exc})"
        time.sleep(poll_interval)

    raise TimeoutError(
        f"{name} not ready after {timeout:.0f}s. Last seen: {_truncate(last_seen)}"
    )


def _missing_json_keys(raw: bytes, expected: tuple[str, ...]) -> tuple[str, ...]:
    """Return which of ``expected`` are absent from a JSON object body.

    Returns an empty tuple when there is nothing to check, when the body is not
    JSON, or when it is JSON but not an object -- all of which mean "this is
    not the payload we were promised", so the caller keeps polling.
    """
    if not expected:
        return ()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return expected
    if not isinstance(payload, dict):
        return expected
    return tuple(key for key in expected if key not in payload)


def _read_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - the status alone is still useful
        return "<body unreadable>"


def _truncate(text: str, limit: int = 400) -> str:
    """Keep a health body short enough to read in a terminal."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "..."
