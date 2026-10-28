"""Environment-driven settings for the local development stack.

Every value is read from the environment, which the server also reads through
``dotenv``. Reading it the same way means the stack manager and the
application cannot disagree about which port Mongo is on or where the wiki
data lives.

Defaults mirror ``selfmemory.config`` and ``selfmemory.wiki_settings``. They
are defaults, not constants: setting the variable overrides them, and
``require()`` refuses to guess when a value is genuinely ambiguous.

What the backend actually needs
-------------------------------
- **MongoDB** holds tenancy (users, organizations, projects, API keys) and the
  wiki run queue. Required: auth resolution, project scoping and job dispatch
  all read from it.
- **The data root** (``SELFMEMORY_DATA_ROOT``, default
  ``~/.selfmemory/data``) is a directory on disk. Uploads land in
  ``orgs/<org>/raw/`` and the compiled, git-backed markdown wikis live in
  ``orgs/<org>/wiki/``. Nothing to start; it is created on first use.
- **The opencode agent** (``SELFMEMORY_AGENT_BIN``) does all model work: each
  ingest or query job runs it, inside a bwrap/docker sandbox when one passes
  a probe, otherwise unconfined in development. It needs model credentials,
  either an ``*_API_KEY`` from its environment allowlist or an ``auth.json``
  under ``SELFMEMORY_AGENT_HOME``. The server itself reads no LLM keys.

There is no vector store and no embedding service. Qdrant, Ollama and the
``EMBEDDING_PROVIDER`` / ``VECTOR_STORE_PROVIDER`` / ``LLM_*`` variables
belonged to the removed backends and are not read by anything here.

Deliberately absent: credentials. This stack binds to loopback and is for
local development only.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from selfmemory.wiki_settings import WikiSettings
from selfmemory.wiki_settings import load_settings as load_wiki_settings

# Repository root: scripts/devstack/settings.py -> scripts/devstack -> scripts -> root
REPO_ROOT = Path(__file__).resolve().parents[2]

# Loopback only. There is no password on this Mongo, so binding it to all
# interfaces would expose an open database to the network.
LOOPBACK = "127.0.0.1"

# Same vocabulary as selfmemory.wiki_settings, so a flag means the same thing
# to the stack manager and to the server.
_TRUE = frozenset({"1", "true", "yes", "on"})


class ConfigError(RuntimeError):
    """Raised when the environment cannot produce a usable configuration."""


def require(name: str, hint: str) -> str:
    """Return ``name`` from the environment or explain what to set.

    Used where a silent default would send the stack somewhere unexpected.
    Failing here costs a second; booting against the wrong database costs an
    afternoon of confused debugging.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set. {hint}")
    return value


def _env(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _env_flag(name: str, default: bool) -> bool:
    """Read a boolean flag, accepting 1/true/yes/on (case-insensitive).

    Unset or empty means ``default``; any other value means false.
    """
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in _TRUE


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for one local stack."""

    # Application
    api_host: str
    api_port: int
    api_reload: bool

    # Mongo -- tenancy (users, orgs, projects, API keys) and the run queue
    mongo_port: int
    mongo_uri: str

    # Wiki engine: data root on disk, agent binary, isolation policy
    wiki: WikiSettings

    # Behaviour
    start_timeout: float
    strict_port: bool

    @property
    def api_base_url(self) -> str:
        return f"http://{LOOPBACK}:{self.api_port}"

    def health_url(self) -> str:
        return f"{self.api_base_url}/health"

    # -- agent ------------------------------------------------------------

    @property
    def agent_bin_path(self) -> str | None:
        """Resolved path of the opencode binary, or None when it is missing.

        Accepts either a path that exists or a bare name found on PATH, since
        ``SELFMEMORY_AGENT_BIN=opencode`` is a reasonable thing to set.
        """
        configured = self.wiki.agent_bin
        if not configured:
            return None
        if Path(configured).expanduser().is_file():
            return str(Path(configured).expanduser())
        return shutil.which(configured)

    @property
    def agent_auth_file(self) -> Path:
        return self.wiki.agent_home / ".local" / "share" / "opencode" / "auth.json"

    @property
    def agent_key_env(self) -> list[str]:
        """``*_API_KEY`` variables from the agent allowlist that are set."""
        return [
            name
            for name in self.wiki.agent_env
            if name.endswith("_API_KEY") and os.getenv(name, "").strip()
        ]

    @property
    def agent_has_credentials(self) -> bool:
        """Whether the agent can authenticate to a model provider.

        Mirrors ``isolation_report``'s ``agent_auth`` without running the
        isolation probe, so it is cheap enough for preflight.
        """
        return bool(self.agent_key_env) or self.agent_auth_file.exists()

    @property
    def agent_ready(self) -> bool:
        """The binary exists and has credentials; runs can actually succeed."""
        return self.agent_bin_path is not None and self.agent_has_credentials

    def describe_agent(self) -> str:
        """One line: where the binary is and where its credentials come from."""
        binary = self.agent_bin_path or f"{self.wiki.agent_bin} (missing)"
        if self.agent_key_env:
            creds = "credentials via " + ", ".join(self.agent_key_env)
        elif self.agent_auth_file.exists():
            creds = f"credentials via {self.agent_auth_file}"
        else:
            creds = "NO credentials"
        return f"{binary}; {creds}"

    # -- description ------------------------------------------------------

    def describe_services(self) -> list[tuple[str, str, str]]:
        """Return probeable (name, endpoint, purpose) rows.

        Only things with a socket belong here, because callers run a network
        probe over each row. The wiki data root is a directory on disk and is
        reported separately by ``describe_wiki()``.
        """
        return [
            ("api", self.api_base_url, "SelfMemory HTTP API"),
            (
                "mongodb",
                f"{LOOPBACK}:{self.mongo_port}",
                "tenancy + wiki run queue",
            ),
        ]

    def describe_wiki(self) -> str:
        """One-line description of the data root: path, existence, org count."""
        root = self.wiki.data_root
        if not root.exists():
            return f"{root} (absent -- created on first upload)"
        orgs_root = self.wiki.orgs_root
        orgs = (
            sum(1 for p in orgs_root.iterdir() if p.is_dir())
            if orgs_root.is_dir()
            else 0
        )
        noun = "org" if orgs == 1 else "orgs"
        return f"{root} ({orgs} {noun})"


def load_settings(env_file: Path | None = None) -> Settings:
    """Load ``.env`` then resolve settings from the environment.

    ``load_dotenv`` does not overwrite variables already present in the
    environment, so an explicit ``MONGODB_PORT=... make run`` still wins over
    the file. That ordering is deliberate: ad-hoc overrides should not require
    editing a tracked file.
    """
    dotenv_path = env_file or REPO_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)

    return Settings(
        api_host=_env("SELFMEMORY_SERVER_HOST", "0.0.0.0"),
        api_port=_env_int("SELFMEMORY_SERVER_PORT", 8081),
        api_reload=_env_flag("API_RELOAD", True),
        mongo_port=_env_int("MONGODB_PORT", 27017),
        mongo_uri=_env("MONGODB_URI", f"mongodb://{LOOPBACK}:27017/selfmemory"),
        # Read after load_dotenv so SELFMEMORY_* values from .env are seen,
        # exactly as the server sees them.
        wiki=load_wiki_settings(),
        start_timeout=_env_int("DEVSTACK_TIMEOUT", 180),
        # Off by default: falling back to a free port keeps `make run` working
        # when something unrelated holds the configured one. Turn on when the
        # exact port matters, e.g. a frontend proxying to it.
        strict_port=_env_flag("DEVSTACK_STRICT_PORT", False),
    )
