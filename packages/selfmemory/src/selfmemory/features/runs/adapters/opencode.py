"""Running the agent: opencode, inside the mount set the caller is entitled to.

All model work happens here. There is no other LLM path in the backend:
ingest, query and lint are each one ``opencode run`` with a prompt rendered
from ``schema/command/<cmd>.md`` and a dedicated agent definition
(``selfmemory-ingest`` can write, ``selfmemory-query`` cannot).

opencode's ``--format json`` stream is one JSON object per line. The events
consumed are::

    {"type":"text","sessionID":..,"part":{"text":..}}
    {"type":"tool_use","part":{"tool":"read","state":{"status":..,"title":..}}}
    {"type":"step_finish","part":{"tokens":{..},"cost":0.0}}
    {"type":"error","error":{"type":..,"message":..}}
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from importlib import resources
from typing import TYPE_CHECKING

from selfmemory.platform.sandbox.sandbox import RunSpec, build_argv, runner_for

if TYPE_CHECKING:
    from pathlib import Path

    from selfmemory.platform.sandbox.isolation import IsolationStatus
    from selfmemory.wiki_settings import WikiSettings

__all__ = [
    "RunPlan",
    "COMMANDS",
    "render_prompt",
    "agent_argv",
    "spawn_agent",
    "parse_event",
    "kill_run",
    "install_agent_config",
]

COMMANDS = ("ingest", "query", "lint")
AGENT_FOR = {
    "ingest": "selfmemory-ingest",
    "query": "selfmemory-query",
    "lint": "selfmemory-query",
}


@dataclass
class RunPlan:
    """Everything one run needs, resolved and authorized by the caller."""

    command: str
    message: str
    org_root: Path
    read_dirs: list[Path]
    write_dir: Path | None
    mask_dirs: list[Path] = field(default_factory=list)
    session_id: str | None = None
    actor: str = ""
    # HOME for this run: per (organization, owner), never shared between
    # tenants. opencode keeps session transcripts -- including the content of
    # every file a run read -- under HOME, so a shared one would let any run
    # read another tenant's history. ``None`` uses the template home.
    home: Path | None = None
    # Unique per run; names the container so a kill reaches it.
    run_id: str = ""
    # Human names for the opaque scope directories, so the agent can say
    # "the Payments project" instead of a database id.
    scope_labels: dict[str, str] = field(default_factory=dict)


def _schema_text(*parts: str) -> str:
    return (
        resources.files("selfmemory.features.runs")
        .joinpath("schema", *parts)
        .read_text(encoding="utf-8")
    )


def render_prompt(plan: RunPlan) -> str:
    if plan.command not in COMMANDS:
        raise ValueError(f"unknown command: {plan.command}")
    template = _schema_text("command", f"{plan.command}.md")
    rel = lambda p: p.relative_to(plan.org_root).as_posix()  # noqa: E731
    lines = [
        "Your working directory is this organization's root.",
    ]
    if plan.write_dir is not None:
        lines.append(
            f"SCOPE_ROOT for this run is {rel(plan.write_dir)}. You may write only inside it."
        )
    else:
        lines.append("This run is read-only. Do not attempt to write any file.")
    readable = [rel(d) for d in plan.read_dirs]
    if readable:
        lines.append("Readable directories: " + ", ".join(readable) + ".")
    if plan.scope_labels:
        lines.append(
            "Scope names: "
            + "; ".join(f"{k} = {v}" for k, v in sorted(plan.scope_labels.items()))
            + "."
        )
    return "\n".join(lines) + "\n\n" + template.replace("$ARGUMENTS", plan.message)


def agent_argv(settings: WikiSettings, plan: RunPlan, binary: str) -> list[str]:
    argv = [
        binary,
        "run",
        "--format",
        "json",
        "--auto",
        "--agent",
        AGENT_FOR[plan.command],
    ]
    if settings.agent_standalone:
        argv.append("--standalone")
    if settings.agent_model:
        argv += ["--model", settings.agent_model]
    if plan.session_id:
        argv += ["--session", plan.session_id]
    argv.append(render_prompt(plan))
    return argv


def _agent_env(settings: WikiSettings, plan: RunPlan) -> dict[str, str]:
    env = {}
    for name in settings.agent_env:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    env["SCOPE_ROOT"] = str(plan.write_dir or plan.org_root)
    env["SELFMEMORY_USER"] = plan.actor
    return env


def install_agent_config(settings: WikiSettings) -> None:
    """Write the agent definitions and global rules into the agent's HOME.

    The agent home is the only directory the sandbox mounts as ``HOME``, so
    configuration placed anywhere else never reaches a run. ``opencode.json``
    is written only when absent: operators put their provider and model there.
    """
    cfg = settings.agent_home / ".config" / "opencode"
    (cfg / "agent").mkdir(parents=True, exist_ok=True)
    (cfg / "AGENTS.md").write_text(_schema_text("AGENTS.md"), encoding="utf-8")
    for name in ("selfmemory-ingest.md", "selfmemory-query.md"):
        (cfg / "agent" / name).write_text(_schema_text("agent", name), encoding="utf-8")
    if not (cfg / "opencode.json").exists():
        (cfg / "opencode.json").write_text(
            _schema_text("opencode.json"), encoding="utf-8"
        )
    settings.agent_home.chmod(0o700)


def prepare_run_home(settings: WikiSettings, home: Path) -> Path:
    """Create a run HOME from the template agent home.

    The template (``settings.agent_home``) holds the operator's opencode
    config and credentials. Each owner's home gets a fresh copy of the config
    and of ``auth.json`` before every run, and keeps its own session storage
    so follow-up questions in a chat can continue their session.
    """
    template_cfg = settings.agent_home / ".config" / "opencode"
    cfg = home / ".config" / "opencode"
    if template_cfg.is_dir():
        if cfg.exists():
            shutil.rmtree(cfg)
        shutil.copytree(template_cfg, cfg, symlinks=False)
    auth = settings.agent_home / ".local" / "share" / "opencode" / "auth.json"
    if auth.is_file():
        dest = home / ".local" / "share" / "opencode" / "auth.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(auth, dest)
        dest.chmod(0o600)
    home.mkdir(parents=True, exist_ok=True)
    home.chmod(0o700)
    return home


def spawn_agent(
    settings: WikiSettings, status: IsolationStatus, plan: RunPlan
) -> subprocess.Popen:
    """Start the run. Confined when a sandbox passed its probe; otherwise only
    reachable at all because the operator did not require isolation or
    acknowledged running without it (``require_isolation`` gates that)."""
    env = _agent_env(settings, plan)
    home = (
        prepare_run_home(settings, plan.home)
        if plan.home is not None
        else settings.agent_home
    )
    popen_kw = {
        "stdin": subprocess.DEVNULL,  # opencode blocks reading piped stdin otherwise
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "start_new_session": True,  # own process group, so cancel kills the tree
    }
    if status.kind is None:
        argv = agent_argv(settings, plan, settings.agent_bin)
        home.mkdir(parents=True, exist_ok=True)
        return subprocess.Popen(
            argv,
            cwd=plan.org_root,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(home),
                **env,
            },
            **popen_kw,
        )
    in_image = settings.agent_in_image and status.kind == "container"
    binary = settings.in_image_agent if in_image else settings.agent_bin
    spec = RunSpec(
        read_dirs=plan.read_dirs,
        write_dir=plan.write_dir,
        agent_home=home,
        agent_bin=settings.agent_bin,
        cwd=plan.org_root,
        argv=agent_argv(settings, plan, binary),
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", **env},
        mask_dirs=plan.mask_dirs,
        agent_in_image=in_image,
        image=settings.sandbox_image,
        name=f"selfmemory-run-{plan.run_id}" if plan.run_id else None,
    )
    runner = runner_for(status.kind)
    proc = subprocess.Popen(
        [runner, *build_argv(status.kind, spec)],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        **popen_kw,
    )
    if status.kind == "container" and spec.name:
        # Killing the `docker run` client does not stop the container.
        proc.container_kill = [runner, "kill", spec.name]  # type: ignore[attr-defined]
    return proc


def kill_run(proc: subprocess.Popen, grace_s: float = 5.0) -> None:
    """Stop the container (if any), then SIGTERM the run's process group and
    SIGKILL it after a grace period."""
    container_kill = getattr(proc, "container_kill", None)
    if container_kill:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                container_kill,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=15,
                check=False,
            )
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)


def parse_event(line: str) -> list[dict]:
    """Translate one opencode JSON line into zero or more run events."""
    line = line.strip()
    if not line.startswith("{"):
        return []
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, dict):
        return []
    out: list[dict] = []
    session = raw.get("sessionID")
    if isinstance(session, str) and session:
        out.append({"kind": "session", "session_id": session})
    part = raw.get("part") if isinstance(raw.get("part"), dict) else {}
    kind = raw.get("type")
    if kind == "text":
        text = part.get("text")
        if isinstance(text, str) and text:
            out.append({"kind": "text", "text": text})
    elif kind == "tool_use":
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        out.append(
            {
                "kind": "tool",
                "tool": str(part.get("tool") or "tool"),
                "title": str(state.get("title") or ""),
                "status": str(state.get("status") or ""),
            }
        )
    elif kind == "step_finish":
        out.append(
            {
                "kind": "usage",
                "tokens": part.get("tokens") or {},
                "cost": part.get("cost") or 0,
            }
        )
    elif kind == "error":
        err = raw.get("error") if isinstance(raw.get("error"), dict) else {}
        out.append(
            {
                "kind": "error",
                "message": str(err.get("message") or "agent error")[:2000],
            }
        )
    return out
