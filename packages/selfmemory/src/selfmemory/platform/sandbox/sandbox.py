"""Confinement for agent runs, expressed as a mount set.

The boundary is "the agent cannot read a scope it was not handed". A sandbox
starts with an empty view of the filesystem and binds in exactly the
directories the caller is entitled to. Every other tenant's wiki, the server's
environment and its source are not merely off-limits inside the run -- they
are absent.

Two primitives implement the same mount set:

    bwrap      Linux mount namespaces. No daemon, ~10ms per run.
    container  docker/podman. The same on a developer's mac and on the host,
               at the cost of a daemon and ~200ms per run.

Neither is trusted on faith: ``isolation.probe`` runs a real conformance test
on the live host before any agent may start.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "RunSpec",
    "available_kinds",
    "runner_for",
    "build_argv",
    "SYSTEM_RO_PATHS",
]

# Read-only system paths an agent legitimately needs. Enumerated rather than
# "mount / read-only": on a host that also runs the server, / carries the
# server's environment, its source, and the data root itself.
SYSTEM_RO_PATHS = (
    "/usr",
    "/lib",
    "/lib64",
    "/bin",
    "/sbin",
    "/etc/ssl",
    "/etc/ca-certificates",
    "/etc/resolv.conf",
    "/etc/hosts",
    "/etc/nsswitch.conf",
    "/etc/passwd",
    "/etc/group",
    "/etc/localtime",
    "/etc/zoneinfo",
)
DEV_RUNTIME_PATHS = ("/opt/homebrew", "/usr/local", "/home/linuxbrew")


@dataclass
class RunSpec:
    """What one run may see.

    ``read_dirs`` are mounted read-only and ``write_dir`` read-write. Any
    directory in ``mask_dirs`` is hidden under an empty tmpfs after those
    mounts -- this is how a parent project's mount stops exposing the
    sub-projects nested inside it. Readable sub-projects are listed in
    ``read_dirs`` after their parent and so are mounted back on top.
    """

    read_dirs: list[Path]
    write_dir: Path | None
    agent_home: Path
    agent_bin: str
    cwd: Path
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    mask_dirs: list[Path] = field(default_factory=list)
    agent_in_image: bool = False
    image: str = "selfmemory/sandbox:latest"
    name: str | None = None  # container name, so the run can be killed


def _which(name: str) -> str | None:
    return shutil.which(name)


def bwrap_available() -> bool:
    return sys.platform.startswith("linux") and _which("bwrap") is not None


def container_bin() -> str | None:
    for name in ("docker", "podman"):
        path = _which(name)
        if path:
            return path
    return None


def available_kinds() -> list[str]:
    kinds = []
    if bwrap_available():
        kinds.append("bwrap")
    if container_bin():
        kinds.append("container")
    return kinds


def runner_for(kind: str) -> str:
    if kind == "bwrap":
        path = _which("bwrap")
        if not path:
            raise RuntimeError("bwrap is not installed")
        return path
    if kind == "container":
        path = container_bin()
        if not path:
            raise RuntimeError("no container runtime (docker/podman) on PATH")
        return path
    raise RuntimeError(f"unknown sandbox kind: {kind}")


def _ordered_mounts(spec: RunSpec) -> list[tuple[str, Path]]:
    """(mode, dir) in mount order: parents before the children nested in them.

    Masks are placed right after the deepest mounted directory that contains
    them, and readable children come after the masks of their parent.
    """
    entries: list[tuple[str, Path]] = [
        ("ro", d) for d in spec.read_dirs if d.exists() and d != spec.write_dir
    ]
    if spec.write_dir is not None:
        entries.append(("rw", spec.write_dir))
    # A masked directory that is itself mounted needs no mask: its own bind
    # already replaces what the parent mount showed there (and docker refuses
    # two mounts at one destination).
    mounted = {d for _, d in entries}
    entries += [("mask", d) for d in spec.mask_dirs if d not in mounted and d.is_dir()]
    order = {"mask": 0, "ro": 1, "rw": 1}
    return sorted(entries, key=lambda e: (len(e[1].parts), order[e[0]], str(e[1])))


def build_argv(kind: str, spec: RunSpec) -> list[str]:
    """Arguments for the confining runner (``bwrap`` or ``docker``).

    The write directory and agent home are created first: a container bind of a
    missing host path silently becomes an empty in-container directory, so an
    ingest would write into a mount that vanishes with the container.
    """
    if spec.write_dir is not None:
        spec.write_dir.mkdir(parents=True, exist_ok=True)
    spec.agent_home.mkdir(parents=True, exist_ok=True)
    # A sub-project directory that does not exist yet must still be masked:
    # otherwise an ingest into the parent could create it and pre-seed the
    # child scope with content. Create it so there is something to mount
    # over. (.git masks are never created here: an empty .git would read as
    # an existing repository.)
    for d in spec.mask_dirs:
        if d.name != ".git":
            d.mkdir(parents=True, exist_ok=True)
    mounts = _ordered_mounts(spec)

    if kind == "bwrap":
        args = ["--die-with-parent", "--new-session", "--unshare-all", "--share-net"]
        args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        for p in SYSTEM_RO_PATHS + DEV_RUNTIME_PATHS:
            if Path(p).exists():
                args += ["--ro-bind", p, p]
        bin_dir = Path(spec.agent_bin).parent
        if bin_dir.is_dir() and bin_dir != Path("/"):
            args += ["--ro-bind", str(bin_dir), str(bin_dir)]
        for mode, d in mounts:
            if mode == "mask":
                args += ["--tmpfs", str(d)]
            elif mode == "rw":
                args += ["--bind", str(d), str(d)]
            else:
                args += ["--ro-bind", str(d), str(d)]
        args += ["--bind", str(spec.agent_home), str(spec.agent_home)]
        args += ["--chdir", str(spec.cwd)]
        args += ["--setenv", "HOME", str(spec.agent_home)]
        args += ["--setenv", "SELFMEMORY_SANDBOXED", "1"]
        for k, v in spec.env.items():
            args += ["--setenv", k, v]
        return [*args, "--", *spec.argv]

    if kind == "container":
        args = [
            "run",
            "--rm",
            "-i",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,size=256m",
        ]
        if spec.name:
            args += ["--name", spec.name]
        if sys.platform.startswith("linux"):
            args += ["--user", f"{os.getuid()}:{os.getgid()}"]
        for mode, d in mounts:
            if mode == "mask":
                args += ["--mount", f"type=tmpfs,destination={d}"]
            else:
                args += ["-v", f"{d}:{d}:{mode}"]
        args += ["-v", f"{spec.agent_home}:{spec.agent_home}:rw"]
        if not spec.agent_in_image:
            args += ["-v", f"{spec.agent_bin}:{spec.agent_bin}:ro"]
        args += ["-w", str(spec.cwd)]
        args += ["-e", f"HOME={spec.agent_home}", "-e", "SELFMEMORY_SANDBOXED=1"]
        for k, v in spec.env.items():
            args += ["-e", f"{k}={v}"]
        return [*args, spec.image, *spec.argv]

    raise RuntimeError(f"unknown sandbox kind: {kind}")


def confinement_check_script(allow_file: Path, secret_file: Path) -> str:
    """Succeeds only if the in-scope file reads and the out-of-scope one does not.

    Exit 8: the sandbox cannot read its own mount (broken). Exit 9: a file
    outside the mount set was readable (not a sandbox at all).
    """
    a, s = shlex.quote(str(allow_file)), shlex.quote(str(secret_file))
    return (
        f"cat {a} >/dev/null 2>&1 || exit 8; "
        f"if cat {s} >/dev/null 2>&1; then exit 9; fi; exit 0"
    )
