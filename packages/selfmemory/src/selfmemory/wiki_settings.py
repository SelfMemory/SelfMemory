"""Runtime settings for the wiki engine.

Everything an operator can turn is read from the environment here, once, into
an immutable value. Modules take a ``WikiSettings`` rather than reading
``os.environ`` themselves, so a test can build one with a temporary data root
and nothing leaks between cases.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["WikiSettings", "load_settings"]

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", "none"}


def _flag(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return default


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except ValueError:
        return default


# Variables the agent is handed. Anything not named here stays out of the run,
# so the server's own secrets (Mongo URI, Ory admin URLs, encryption keys) are
# not reachable from a process the model could be talked into inspecting.
DEFAULT_AGENT_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENROUTER_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "OPENCODE_PERMISSION",
    "OPENCODE_CONFIG",
    "NO_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
)


@dataclass(frozen=True)
class WikiSettings:
    """Immutable configuration for storage, agent runs and isolation."""

    data_root: Path
    agent_home: Path
    agent_bin: str
    agent_model: str | None = None
    agent_env: tuple[str, ...] = DEFAULT_AGENT_ENV
    agent_in_image: bool = True
    # opencode v2 attaches `run` to a shared background service unless told
    # otherwise; a sandboxed run must start its own private server.
    agent_standalone: bool = True
    in_image_agent: str = "opencode"
    sandbox_image: str = "selfmemory/sandbox:latest"
    require_isolation: bool = False
    unisolated_ack: bool = False
    run_timeout_s: int = 600
    max_concurrent_runs: int = 8
    # Fair share across tenants: runs one credential owner / one organization
    # may have going at once, across every worker. Excess jobs wait queued.
    max_runs_per_owner: int = 4
    max_runs_per_org: int = 16
    # Jobs one owner may have waiting in the queue at once; more are refused.
    max_queued_per_owner: int = 100
    # Quotas: runs one user (across all their credentials) / one organization
    # may queue per UTC day. 0 means unlimited. Atomic counters in Mongo.
    max_runs_per_owner_per_day: int = 0
    max_runs_per_org_per_day: int = 0
    # Finished runs (results, event streams) are kept this long, so a caller
    # that disconnected can resubscribe or poll.
    run_retention_s: int = 24 * 3600
    # Agent contexts (A2A ``contextId``) are deleted after this long idle.
    context_idle_ttl_s: int = 3600
    # Agent session homes (opencode transcripts) unused this long are deleted.
    session_home_retention_s: int = 30 * 86400
    # Audit records older than this many days expire; 0 keeps them forever.
    audit_retention_days: int = 0
    upload_max_files: int = 2000
    upload_max_bytes: int = 50 * 1024 * 1024
    worker_enabled: bool = True
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def orgs_root(self) -> Path:
        return self.data_root / "orgs"

    def org_root(self, org_id: str) -> Path:
        """The tree one organization's raw sources and wiki live in."""
        from selfmemory.kernel.safe_paths import safe_segment

        return self.orgs_root / safe_segment(org_id)

    @property
    def probe_root(self) -> Path:
        return self.data_root / ".probe"

    @property
    def trash_root(self) -> Path:
        return self.data_root / ".trash"


def _default_agent_bin() -> str:
    candidates = [
        os.getenv("SELFMEMORY_AGENT_BIN"),
        "/usr/local/bin/opencode",
        str(Path.home() / ".opencode" / "bin" / "opencode"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return next(c for c in candidates if c)


def load_settings(env: dict[str, str] | None = None) -> WikiSettings:
    """Build settings from the environment (or a supplied mapping, for tests)."""
    e = os.environ if env is None else env
    data_root = Path(
        e.get("SELFMEMORY_DATA_ROOT") or Path.home() / ".selfmemory" / "data"
    ).expanduser()
    agent_home = Path(
        e.get("SELFMEMORY_AGENT_HOME") or data_root / ".agent"
    ).expanduser()
    production = (e.get("ENVIRONMENT") or "development").lower() == "production"
    extra_env = tuple(
        n.strip() for n in (e.get("SELFMEMORY_AGENT_ENV") or "").split(",") if n.strip()
    )
    return WikiSettings(
        data_root=data_root,
        agent_home=agent_home,
        agent_bin=e.get("SELFMEMORY_AGENT_BIN") or _default_agent_bin(),
        agent_model=e.get("SELFMEMORY_AGENT_MODEL") or None,
        agent_env=DEFAULT_AGENT_ENV + extra_env,
        agent_in_image=_flag(e.get("SELFMEMORY_AGENT_IN_IMAGE"), True),
        agent_standalone=_flag(e.get("SELFMEMORY_AGENT_STANDALONE"), True),
        in_image_agent=e.get("SELFMEMORY_IN_IMAGE_AGENT") or "opencode",
        sandbox_image=e.get("SELFMEMORY_SANDBOX_IMAGE") or "selfmemory/sandbox:latest",
        require_isolation=_flag(e.get("SELFMEMORY_REQUIRE_ISOLATION"), production),
        unisolated_ack=_flag(e.get("SELFMEMORY_UNISOLATED_ACK"), False),
        run_timeout_s=_int(e.get("SELFMEMORY_RUN_TIMEOUT_S"), 600),
        max_concurrent_runs=max(1, _int(e.get("SELFMEMORY_MAX_CONCURRENT_RUNS"), 8)),
        max_runs_per_owner=max(1, _int(e.get("SELFMEMORY_MAX_RUNS_PER_OWNER"), 4)),
        max_runs_per_org=max(1, _int(e.get("SELFMEMORY_MAX_RUNS_PER_ORG"), 16)),
        run_retention_s=max(60, _int(e.get("SELFMEMORY_RUN_RETENTION_S"), 86400)),
        context_idle_ttl_s=max(60, _int(e.get("SELFMEMORY_CONTEXT_IDLE_TTL_S"), 3600)),
        max_queued_per_owner=max(
            1, _int(e.get("SELFMEMORY_MAX_QUEUED_PER_OWNER"), 100)
        ),
        max_runs_per_owner_per_day=max(
            0, _int(e.get("SELFMEMORY_MAX_RUNS_PER_OWNER_PER_DAY"), 0)
        ),
        max_runs_per_org_per_day=max(
            0, _int(e.get("SELFMEMORY_MAX_RUNS_PER_ORG_PER_DAY"), 0)
        ),
        session_home_retention_s=max(
            3600, _int(e.get("SELFMEMORY_SESSION_HOME_RETENTION_S"), 30 * 86400)
        ),
        audit_retention_days=max(0, _int(e.get("SELFMEMORY_AUDIT_RETENTION_DAYS"), 0)),
        upload_max_files=_int(e.get("SELFMEMORY_UPLOAD_MAX_FILES"), 2000),
        upload_max_bytes=_int(e.get("SELFMEMORY_UPLOAD_MAX_BYTES"), 50 * 1024 * 1024),
        worker_enabled=_flag(e.get("SELFMEMORY_WORKER"), True),
    )
