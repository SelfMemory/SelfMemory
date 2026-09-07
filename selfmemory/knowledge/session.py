"""Running an agent against a materialized workspace.

The agent runtime sits behind a protocol on purpose. It is an external binary
in the path of the product's core read, so it should be replaceable without
touching anything above it -- and a second implementation is what lets the test
suite run with no subprocess and no network.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 180
_CITATION_RE = re.compile(r"\[\[([^\]]+)\]\]|`([a-z0-9][a-z0-9./_-]*)`", re.IGNORECASE)


class AgentSessionError(RuntimeError):
    """The agent runtime failed, timed out, or is not installed."""


@dataclass
class SessionResult:
    text: str
    cited: list[str] = field(default_factory=list)
    raw: str = ""


@runtime_checkable
class AgentRunner(Protocol):
    """Runs one prompt against one directory and returns what it said."""

    def run(
        self, cwd: Path, prompt: str, *, writable: bool, timeout: int
    ) -> SessionResult: ...


def extract_citations(text: str, known: set[str]) -> list[str]:
    """Pull page slugs out of an answer.

    Matches both `[[slug]]` links and backticked paths, then keeps only slugs
    that actually exist -- a model naming a page that is not there is a
    hallucinated citation, and passing it through would make the citation list
    worse than useless.
    """
    found: list[str] = []
    for link, code in _CITATION_RE.findall(text):
        slug = (link or code).strip().removesuffix(".md")
        slug = slug.removeprefix("pages/")
        if slug in known and slug not in found:
            found.append(slug)
    return found


class OpencodeRunner:
    """Drives the opencode binary as a one-shot subprocess.

    ``opencode run --dir`` gives a session per invocation with no server to
    supervise, which is what we want: the process dies with the workspace.
    """

    def __init__(
        self,
        binary: str = "opencode",
        model: str | None = None,
        agent: str | None = None,
    ):
        self.binary = binary
        self.model = model
        self.agent = agent

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def run(
        self,
        cwd: Path,
        prompt: str,
        *,
        writable: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> SessionResult:
        if not self.available():
            raise AgentSessionError(
                f"{self.binary!r} is not on PATH; install opencode or pass a "
                "different AgentRunner"
            )

        cmd = [self.binary, "run", "--dir", str(cwd), "--format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        agent = self.agent or (None if writable else "reader")
        if agent:
            cmd += ["--agent", agent]
        cmd.append(prompt)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
                check=False,
                # Never inherit stdin: under a server process it is not a tty
                # and the agent waits on it forever instead of running.
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentSessionError(f"agent session exceeded {timeout}s") from exc

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:400]
            raise AgentSessionError(f"agent exited {proc.returncode}: {detail}")

        return SessionResult(text=_last_text(proc.stdout), raw=proc.stdout)


def _last_text(stdout: str) -> str:
    """Take the assistant's final message out of the JSON event stream.

    Events carry ``{"type": "text", "part": {"text": ...}}``; tool calls carry
    their own output under ``part.state``, which must not be mistaken for the
    answer. The stream shape is not a stability guarantee, so fall back through
    looser shapes and finally to the raw output rather than failing a session
    that otherwise succeeded.
    """
    texts: list[str] = []
    loose: list[str] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        part = event.get("part")
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
                continue

        for key in ("text", "content", "message"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                loose.append(value)
                break

    if texts:
        return texts[-1].strip()
    if loose:
        return loose[-1].strip()

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip()

    if isinstance(parsed, dict):
        for key in ("text", "content", "message", "output"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return stdout.strip()
