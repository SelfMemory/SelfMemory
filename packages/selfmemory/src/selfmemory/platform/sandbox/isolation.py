"""Isolation policy: verify the boundary on this host, or refuse to run agents.

Confinement is never inferred from configuration. A probe mounts one
directory, tries to read a file outside it, and only counts the boundary as
present when that read fails. A second probe proves the agent binary can
actually start inside the sandbox -- a sandbox that is "secure" only because
nothing can run in it is not useful.

When no primitive passes and isolation is required (the default in
production), every agent run is refused. ``SELFMEMORY_UNISOLATED_ACK=1`` lets
an operator consciously accept unconfined runs; the health endpoint says so.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from selfmemory.platform.sandbox.sandbox import (
    RunSpec,
    available_kinds,
    build_argv,
    confinement_check_script,
    runner_for,
)

if TYPE_CHECKING:
    pass

    from selfmemory.wiki_settings import WikiSettings

__all__ = [
    "IsolationStatus",
    "IsolationUnavailableError",
    "get_isolation",
    "require_isolation",
    "reset_isolation_cache",
]

PROBE_TTL_S = 30.0


@dataclass
class Check:
    ok: bool
    detail: str


@dataclass
class IsolationStatus:
    kind: str | None  # "bwrap" | "container" | None (unconfined)
    ok: bool
    blocked: bool
    required: bool
    acknowledged: bool
    detail: str
    checks: dict[str, Check] = field(default_factory=dict)
    checked_at: float = 0.0

    @property
    def unconfined(self) -> bool:
        return self.kind is None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["unconfined"] = self.unconfined
        return d


class IsolationUnavailableError(RuntimeError):
    def __init__(self, status: IsolationStatus):
        super().__init__(
            "Agent runs are disabled: no verified sandbox on this host. "
            f"{status.detail}. Install bubblewrap or docker, or set "
            "SELFMEMORY_UNISOLATED_ACK=1 to accept running agents with "
            "unrestricted filesystem access."
        )
        self.status = status


def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stderr or proc.stdout).strip()
    except subprocess.TimeoutExpired:
        return 124, f"probe timed out after {timeout}s"
    except OSError as e:
        return 1, str(e)


def _base(path: str) -> str:
    return Path(path).name


def _tail(text: str) -> str:
    return " | ".join(text.splitlines()[-3:])


def _probe_kind(kind: str, settings: WikiSettings) -> dict[str, Check]:
    try:
        runner = runner_for(kind)
    except RuntimeError as e:
        return {
            "primitive": Check(False, str(e)),
            "confinement": Check(False, "not attempted"),
            "agent": Check(False, "not attempted"),
        }
    primitive = Check(True, f"{kind} via {_base(runner)}")
    stamp = f"p{os.getpid()}-{int(time.time() * 1000):x}"
    base = settings.probe_root / stamp
    allow, secret = base / "allow", base / "secret"
    try:
        allow.mkdir(parents=True, exist_ok=True)
        secret.mkdir(parents=True, exist_ok=True)
        (allow / "ok.txt").write_text("selfmemory-probe")
        (secret / "leak.txt").write_text("selfmemory-probe")

        def spec(argv: list[str]) -> RunSpec:
            return RunSpec(
                read_dirs=[allow],
                write_dir=None,
                agent_home=settings.agent_home,
                agent_bin=settings.agent_bin,
                cwd=allow,
                argv=argv,
                agent_in_image=settings.agent_in_image,
                image=settings.sandbox_image,
            )

        script = confinement_check_script(allow / "ok.txt", secret / "leak.txt")
        code, out = _run([runner, *build_argv(kind, spec(["/bin/sh", "-c", script]))])
        if code == 0:
            confinement = Check(
                True, "in-scope file readable, out-of-scope file unreachable"
            )
        elif code == 9:
            confinement = Check(
                False, "FAILED: a file outside the mount set was readable"
            )
        elif code == 8:
            hint = (
                " Docker Desktop shares only the home tree by default; put "
                "SELFMEMORY_DATA_ROOT under $HOME or add it to file sharing."
                if kind == "container" and os.uname().sysname == "Darwin"
                else ""
            )
            confinement = Check(
                False,
                f"FAILED: the sandbox could not read its own in-scope file.{hint}",
            )
        else:
            confinement = Check(False, f"FAILED: exit {code}: {_tail(out)}")

        agent_cmd = (
            settings.in_image_agent
            if settings.agent_in_image and kind == "container"
            else settings.agent_bin
        )
        code, out = _run([runner, *build_argv(kind, spec([agent_cmd, "--version"]))])
        # Proving the agent *starts* is the point; only "cannot execute" fails.
        cannot = code in (126, 127) or any(
            s in out.lower()
            for s in (
                "executable file not found",
                "exec format error",
                "no such file or directory",
                "unable to find image",
                "pull access denied",
            )
        )
        agent = (
            Check(
                False,
                f"FAILED: {_base(agent_cmd)} cannot run: exit {code}: {_tail(out)}",
            )
            if cannot
            else Check(True, f"{_base(agent_cmd)} starts under confinement")
        )
        return {"primitive": primitive, "confinement": confinement, "agent": agent}
    except OSError as e:
        return {
            "primitive": primitive,
            "confinement": Check(False, f"FAILED: probe error: {e}"),
            "agent": Check(False, "not attempted"),
        }
    finally:
        shutil.rmtree(base, ignore_errors=True)


_lock = threading.Lock()
_cached: IsolationStatus | None = None


def _finish(
    settings: WikiSettings, kind: str | None, ok: bool, detail: str, checks: dict
) -> IsolationStatus:
    required, ack = settings.require_isolation, settings.unisolated_ack
    return IsolationStatus(
        kind=kind if ok else None,
        ok=ok,
        blocked=required and not ok and not ack,
        required=required,
        acknowledged=ack,
        detail=detail,
        checks=checks,
        checked_at=time.time(),
    )


def get_isolation(settings: WikiSettings, force: bool = False) -> IsolationStatus:
    """Current status, probing when the cached result is older than 30s."""
    global _cached
    with _lock:
        if (
            not force
            and _cached is not None
            and time.time() - _cached.checked_at < PROBE_TTL_S
        ):
            return _cached
        kinds = available_kinds()
        if not kinds:
            status = _finish(
                settings,
                None,
                False,
                "no sandbox primitive found: install bubblewrap (Linux) or docker",
                {
                    "primitive": Check(
                        False, "neither bwrap nor docker/podman on PATH"
                    ),
                    "confinement": Check(False, "not attempted"),
                    "agent": Check(False, "not attempted"),
                },
            )
        else:
            first: tuple[str, dict] | None = None
            chosen: tuple[str, dict] | None = None
            for kind in kinds:
                checks = _probe_kind(kind, settings)
                if all(c.ok for c in checks.values()):
                    chosen = (kind, checks)
                    break
                first = first or (kind, checks)
            if chosen:
                kind, checks = chosen
                status = _finish(
                    settings,
                    kind,
                    True,
                    f"{kind}: {checks['confinement'].detail}",
                    checks,
                )
            else:
                kind, checks = first  # type: ignore[misc]
                status = _finish(
                    settings,
                    None,
                    False,
                    f"probe failed ({kind}): {checks['confinement'].detail}; "
                    f"agent: {checks['agent'].detail}",
                    checks,
                )
        _cached = status
        return status


def require_isolation(settings: WikiSettings) -> IsolationStatus:
    """Gate for every path about to start an agent. Raises instead of degrading."""
    status = get_isolation(settings)
    if status.blocked:
        raise IsolationUnavailableError(status)
    return status


def reset_isolation_cache() -> None:
    global _cached
    with _lock:
        _cached = None


def isolation_report(settings: WikiSettings) -> dict:
    """The status plus whether the agent has credentials to work with."""
    status = get_isolation(settings).to_dict()
    home: Path = settings.agent_home
    auth = home / ".local" / "share" / "opencode" / "auth.json"
    config = home / ".config" / "opencode" / "opencode.json"
    status["agent_auth"] = auth.exists() or any(
        os.environ.get(n) for n in settings.agent_env if n.endswith("_API_KEY")
    )
    status["agent_config"] = config.exists()
    return status
