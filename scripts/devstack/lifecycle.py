"""Lifecycle for the local development stack.

Order matters. The API needs Mongo for tenancy and the wiki run queue, so a
naive "start everything and see" script produces a confusing crash instead of
a clear message. Proving each dependency ready first means the API either
starts or fails with a sentence explaining what is missing.

Sequence:
    1. preflight   - tools present, config sane, agent binary and credentials
    2. mongodb     - up and answering, for tenancy and the run queue
    3. api         - started, and /health reports ready

Nothing else is started. The wiki data root is a directory on disk, and all
model work happens inside per-job ``opencode`` agent runs, so there is no
vector store, embedding service or LLM client to bring up.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error

from scripts.devstack.settings import LOOPBACK, REPO_ROOT, Settings, load_settings
from scripts.devstack.waiters import ProbeError, wait_for_http, wait_for_port

COMPOSE_FILE = REPO_ROOT / "deploy" / "docker-compose.yml"

# Only Mongo is managed here. The wiki is a directory on disk and the agent is
# a binary run per job; neither is a service.
MANAGED_SERVICES = ("mongodb",)

# Keys SelfMemory's /health always returns. Checking them stops an unrelated
# app on the same port from being reported as a healthy API: a status code
# alone is satisfied by anything that answers 200, and a developer machine
# often has something else on :8081.
HEALTH_PAYLOAD_KEYS = ("status", "checks")

# How far above the configured port to look for a free one. Small enough that
# the printed URL stays recognisable, large enough to clear a couple of
# unrelated dev servers.
PORT_SCAN_RANGE = 20


class PreflightError(RuntimeError):
    """A prerequisite for running the stack is missing."""


def _log(message: str) -> None:
    print(f"[devstack] {message}", flush=True)


def _warn(message: str) -> None:
    print(f"[devstack] warning: {message}", flush=True)


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------


def check_tools(settings: Settings) -> None:
    """Verify the binaries the stack shells out to are on PATH.

    Raises:
        PreflightError: A required binary is missing, with the install hint.
    """
    missing: list[str] = []

    if not shutil.which("docker"):
        missing.append("docker (https://docs.docker.com/get-docker/)")
    if not COMPOSE_FILE.exists():
        missing.append(f"{COMPOSE_FILE.name} (expected at {COMPOSE_FILE})")

    if missing:
        raise PreflightError(
            "Cannot start the stack, missing:\n  - " + "\n  - ".join(missing)
        )


def check_config(settings: Settings) -> None:
    """Report configuration that will otherwise fail in a confusing place.

    Nothing here is fatal on its own. Each item is a case where the stack would
    start, look healthy, and then fail on first use -- or refuse to boot with a
    message that does not name the cause.
    """
    if not (REPO_ROOT / ".env").exists():
        _warn("no .env file; falling back to built-in defaults")

    if settings.agent_bin_path is None:
        _warn(
            f"opencode agent binary not found at {settings.wiki.agent_bin}. "
            "The API will start, but every ingest and query run will fail. "
            "Install opencode or set SELFMEMORY_AGENT_BIN."
        )

    if not settings.agent_has_credentials:
        keys = ", ".join(n for n in settings.wiki.agent_env if n.endswith("_API_KEY"))
        _warn(
            "the opencode agent has no model credentials: none of "
            f"{keys} is set and {settings.agent_auth_file} does not exist. "
            "Runs will fail until one is provided."
        )


# --------------------------------------------------------------------------
# mongodb
# --------------------------------------------------------------------------


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command against the repo's compose file."""
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def docker_daemon_up() -> bool:
    """Return whether the Docker daemon is accepting connections."""
    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    return result.returncode == 0


def port_in_use(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return whether something is already listening on ``host:port``.

    A connect attempt, not a bind attempt: asking the OS whether *we* could
    bind would race whoever holds it and would report false while the port is
    in TIME_WAIT from a previous run.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def api_already_serving(settings: Settings) -> bool:
    """Return whether a healthy SelfMemory API is already on the port.

    Uses the same payload check as the readiness probe, so an unrelated app
    that merely answers 200 on ``/health`` does not count as ours.
    """
    try:
        wait_for_http(
            settings.health_url(),
            timeout=2.0,
            poll_interval=0.2,
            expect_json_keys=HEALTH_PAYLOAD_KEYS,
        )
        return True
    except TimeoutError:
        return False


def start_mongodb(settings: Settings) -> None:
    """Ensure Mongo is reachable, starting the container only if needed.

    Reuses a Mongo that is already listening rather than fighting it for the
    port. A native ``mongod`` from Homebrew on 27017 is a perfectly good
    Mongo, and `docker compose up` against an occupied port fails with a bind
    error that reads like a configuration mistake.

    Raises:
        PreflightError: The Docker daemon is not running and no Mongo is up.
        TimeoutError: A container started but never became reachable.
    """
    if port_in_use(LOOPBACK, settings.mongo_port):
        _log(
            f"mongodb already listening on {LOOPBACK}:{settings.mongo_port}; "
            "reusing it instead of starting the container"
        )
        return

    if not docker_daemon_up():
        raise PreflightError(
            f"Nothing is listening on {LOOPBACK}:{settings.mongo_port} and the "
            "Docker daemon is not running, so the container cannot be started.\n"
            "Either start Docker (colima start / launch Docker Desktop), or run "
            "a MongoDB yourself on that port."
        )

    _log("starting mongodb")
    result = _compose("up", "-d", *MANAGED_SERVICES, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"docker compose up failed:\n{result.stdout}\n{result.stderr}"
        )

    # Port, not container state: 'running' means the process exists, not that
    # Mongo finished initialising its data files.
    wait_for_port(
        LOOPBACK, settings.mongo_port, settings.start_timeout, label="mongodb"
    )
    _log(f"mongodb ready on {LOOPBACK}:{settings.mongo_port}")


def stop_containers(*, volumes: bool = False) -> None:
    """Stop the managed containers.

    Data volumes survive by default; ``volumes=True`` deletes them, which
    throws away every local user, project and API key. That is why it is
    opt-in rather than a side effect of a plain ``down``.
    """
    if not docker_daemon_up():
        _log("docker daemon not running; nothing to stop")
        return

    args = ["down", "--volumes"] if volumes else ["down"]
    _log("stopping mongodb" + (" and deleting volumes" if volumes else " (data kept)"))
    result = _compose(*args, check=False)
    if result.returncode != 0:
        _log(f"compose down reported: {result.stderr.strip()}")


# --------------------------------------------------------------------------
# api
# --------------------------------------------------------------------------


def start_api(settings: Settings) -> tuple[subprocess.Popen[bytes], Settings]:
    """Start uvicorn and return the process plus the settings it actually uses.

    The returned settings may carry a different port from the one passed in,
    when the configured port was occupied and ``_check_api_port`` moved it.
    Callers must use the returned value for readiness checks and the startup
    banner, or they will report a URL that nothing is listening on.

    The child gets its own session so Ctrl-C here does not race uvicorn's
    reload supervisor; we terminate the whole group on the way out.

    Raises:
        PreflightError: The port is held by another app and no free port was
            found, or strict mode refused the fallback.
    """
    _check_api_port(settings)

    port = _resolve_api_port(settings)
    settings = dataclasses.replace(settings, api_port=port)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "selfmemory.apps.api:app",
        "--host",
        settings.api_host,
        "--port",
        str(settings.api_port),
    ]
    if settings.api_reload:
        cmd.append("--reload")

    _log(f"starting API: {' '.join(cmd)}")
    # New session detaches from our terminal's signal group; see above.
    process = subprocess.Popen(
        cmd, cwd=REPO_ROOT, start_new_session=True, env=_child_env(settings)
    )
    return process, settings


def _resolve_api_port(settings: Settings) -> int:
    """Return the port the API will actually bind.

    Same decision ``_check_api_port`` makes, without re-announcing it, so the
    caller can hand the real port to the server and print it. Kept separate
    because the check runs for its error reporting and this runs for its value.
    """
    port = settings.api_port
    if not port_in_use(LOOPBACK, port) or api_already_serving(settings):
        return port
    if settings.strict_port:
        return port  # _check_api_port already raised
    return _next_free_port(port) or port


def _child_env(settings: Settings) -> dict[str, str]:
    """Environment for the API process: a copy of ours, passed through.

    A copy so the child can be adjusted without mutating this process. The
    server reads the same ``.env`` itself, so nothing needs injecting.
    """
    return dict(os.environ)


def _check_api_port(settings: Settings) -> None:
    """Decide which port the API should bind, falling back when occupied.

    A developer machine routinely has something unrelated on the API port. A
    startup script that dies there is a daily nuisance for a problem the user
    cannot avoid, so the port moves up to the next free one and says so.

    The alternative -- letting uvicorn bind and fail -- produces a stack trace
    ending in ``OSError: [Errno 48] Address already in use``, which names
    neither the port nor the process holding it.

    Set ``DEVSTACK_STRICT_PORT=1`` to turn the fallback off and fail instead,
    which is what you want if something downstream depends on the exact port.

    An already-healthy SelfMemory API on the port is not a conflict: it is left
    alone, since it is serving exactly what was asked for.

    Raises:
        PreflightError: The port is held by another app and strict mode is on,
            or no free port was found within the scan window.
    """
    port = settings.api_port
    if not port_in_use(LOOPBACK, port):
        return

    if api_already_serving(settings):
        _log(f"a SelfMemory API is already serving on {settings.api_base_url}")
        return

    if settings.strict_port:
        raise PreflightError(
            f"Port {port} is already in use by something that is not a SelfMemory "
            "API, and DEVSTACK_STRICT_PORT is set.\n"
            f"  find it:  lsof -nP -iTCP:{port} -sTCP:LISTEN\n"
            f"  or:       SELFMEMORY_SERVER_PORT={port + 1} make run"
        )

    fallback = _next_free_port(port)
    if fallback is None:
        raise PreflightError(
            f"Port {port} is held by another app and none of the next "
            f"{PORT_SCAN_RANGE} ports are free either.\n"
            f"  find the holder:  lsof -nP -iTCP:{port} -sTCP:LISTEN"
        )

    _warn(
        f"port {port} is held by another application, so the API is starting on "
        f"{fallback} instead. Anything hard-coded to {port} will not reach it."
    )
    _log(f"  holder:  lsof -nP -iTCP:{port} -sTCP:LISTEN")
    _log(f"  fix:     SELFMEMORY_SERVER_PORT={port} in .env once that app stops")


def _next_free_port(start: int) -> int | None:
    """Return the first free port above ``start``, or None.

    Scans upward rather than asking the OS for an ephemeral port: staying in a
    predictable neighbourhood keeps the printed URL recognisable and avoids
    landing somewhere a browser treats as unsafe.
    """
    for candidate in range(start + 1, start + 1 + PORT_SCAN_RANGE):
        if not port_in_use(LOOPBACK, candidate):
            return candidate
    return None


def find_running_api_port(settings: Settings) -> int | None:
    """Return the port a SelfMemory API is actually serving on, or None.

    Looks for the app by identity rather than by port, because the port it
    ended up on is not recorded anywhere. ``up`` may have moved it off the
    configured one when something else held that port, so a later ``status``
    would otherwise scan past the running server, treat it as just another
    occupied port, and report the one after it.

    Checks the configured port first, then the fallback window.
    """
    candidates = [
        settings.api_port,
        *range(settings.api_port + 1, settings.api_port + 1 + PORT_SCAN_RANGE),
    ]
    for port in candidates:
        probe = dataclasses.replace(settings, api_port=port)
        if not port_in_use(LOOPBACK, port):
            continue
        if api_already_serving(probe):
            return port
    return None


def wait_for_api(settings: Settings, process: subprocess.Popen[bytes]) -> None:
    """Block until ``/health`` reports ready.

    Fails early if the server process has already exited, rather than waiting
    out the full timeout on something that died in the first second.
    """
    deadline = time.monotonic() + settings.start_timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"API exited during startup with code {exit_code}. "
                f"Run `make run-api` to watch its output directly."
            )
        try:
            wait_for_http(
                settings.health_url(),
                poll_interval=1.0,
                timeout=2.0,
                label="api /health",
                expect_json_keys=HEALTH_PAYLOAD_KEYS,
            )
            return
        except TimeoutError:
            continue

    raise TimeoutError(
        f"API did not report healthy within {settings.start_timeout:.0f}s. "
        f"Check {settings.health_url} and the server logs."
    )


def stream_until_interrupt(process: subprocess.Popen[bytes]) -> int:
    """Forward the child's output until it exits or the user interrupts."""
    try:
        return process.wait()
    except KeyboardInterrupt:
        _log("interrupted; stopping API")
        terminate_group(process)
        return 0


def terminate_group(process: subprocess.Popen[bytes], grace: float = 5.0) -> None:
    """Stop the API and any reload child it spawned.

    Sends SIGTERM to the group, then SIGKILL if it is still alive after
    ``grace``. SIGKILL alone would skip uvicorn's shutdown handlers; SIGTERM
    alone would hang forever on a wedged process.
    """
    if process.poll() is not None:
        return

    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue
    _log("API did not exit; it may need a manual kill")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def up(settings: Settings | None = None) -> int:
    """Bring the full stack up and block until interrupted."""
    settings = settings or load_settings()

    _log("preflight")
    check_tools(settings)
    check_config(settings)

    # Refuse to add a second server. Because the port falls back when the
    # configured one is taken, a second `make run` used to land on yet another
    # port and quietly succeed -- leaving two stacks running on different ports
    # with no way to tell which one you are meant to open. Reporting the
    # existing one is the truthful answer: it is already serving.
    existing = find_running_api_port(settings)
    if existing is not None:
        url = f"http://{LOOPBACK}:{existing}"
        _log(f"a SelfMemory API is already running at {url}")
        _log(f"  open:   {url}/docs")
        _log(f"  health: {url}/health")
        _log("")
        _log("Not starting another one. Stop it first with:")
        _log("  pkill -f 'uvicorn selfmemory.apps.api:app'")
        return 0

    start_mongodb(settings)

    process, effective = start_api(settings)
    try:
        wait_for_api(effective, process)
        _print_ready(effective)
        return stream_until_interrupt(process)
    finally:
        terminate_group(process)


def down(settings: Settings | None = None, *, volumes: bool = False) -> int:
    """Stop the containers."""
    stop_containers(volumes=volumes)
    return 0


def status(settings: Settings | None = None) -> int:
    """Report each subsystem. Always exits 0; this is for a human reading it."""
    settings = settings or load_settings()

    # Find the API by identity, not by port. `up` may have moved it off the
    # configured port, and the fallback is not recorded anywhere, so probing the
    # configured port alone would report a URL the server is not on.
    running = find_running_api_port(settings)
    if running is not None:
        if running != settings.api_port:
            _log(
                f"note: the API is on {running}, not the configured {settings.api_port}"
            )
        settings = dataclasses.replace(settings, api_port=running)

    for name, endpoint, purpose in settings.describe_services():
        state = _probe_summary(name, endpoint)
        print(f"  {name:<10} {state:<9} {endpoint}  ({purpose})")

    print(f"  {'wiki':<10} {'dir':<9} {settings.describe_wiki()}")

    agent_state = "ready" if settings.agent_ready else "NOT READY"
    print(f"  {'agent':<10} {agent_state:<9} {settings.describe_agent()}")

    print(f"  {'isolation':<10} {_isolation_summary(settings)}")
    return 0


def _probe_summary(name: str, endpoint: str) -> str:
    """One-word state for a service, without raising."""
    try:
        if name == "api":
            wait_for_http(
                endpoint + "/health",
                timeout=2.0,
                poll_interval=0.2,
                expect_json_keys=HEALTH_PAYLOAD_KEYS,
            )
        elif name == "mongodb":
            host, _, port = endpoint.rpartition(":")
            wait_for_port(host, int(port), timeout=2.0, poll_interval=0.2)
        return "up"
    except (TimeoutError, ProbeError, ValueError, urllib.error.URLError):
        return "down"


def _isolation_summary(settings: Settings) -> str:
    """One line from ``isolation_report``, without raising.

    May run a docker probe that takes a few seconds, which is acceptable for
    ``status`` but is why it is not part of preflight.
    """
    try:
        from selfmemory.platform.sandbox.isolation import isolation_report

        report = isolation_report(settings.wiki)
    except Exception as exc:  # noqa: BLE001 - status must always print
        return f"{'unknown':<9} probe failed: {exc}"

    kind = report.get("kind") or "unconfined"
    if report.get("blocked"):
        state = "BLOCKED"
    elif report.get("ok"):
        state = "ok"
    else:
        state = "warn"  # runs proceed unconfined (development only)
    # The probe detail can quote whole docker errors; `make isolation` has it all.
    detail = " ".join(str(report.get("detail") or "").split())
    if len(detail) > 100:
        detail = detail[:100] + "... (make isolation for the full report)"
    return f"{state:<9} {kind}" + (f"  ({detail})" if detail else "")


def _print_ready(settings: Settings) -> None:
    print("", flush=True)
    print("=" * 64, flush=True)
    print("  SelfMemory is up", flush=True)
    print("=" * 64, flush=True)
    for name, endpoint, purpose in settings.describe_services():
        print(f"  {name:<10} {endpoint}  ({purpose})", flush=True)
    print(f"  {'wiki':<10} {settings.describe_wiki()}", flush=True)
    print(f"  {'agent':<10} {settings.describe_agent()}", flush=True)
    print("", flush=True)
    print(f"  Open in a browser:  {settings.api_base_url}/docs", flush=True)
    print(f"  Service index:      {settings.api_base_url}/", flush=True)
    print(f"  Health:             {settings.health_url()}", flush=True)
    print("")
    print("  There is no web UI and nothing listens on :3000 -- this is an API.")
    print("  /docs is the interactive API browser.")
    print("")
    print("  Bruno      bruno/  -> put the seeded key in bruno/environments/local.yml")
    print("", flush=True)
    print("  Next: seed a project API key to call the endpoints")
    print("    uv run python scripts/dev_seed_api_key.py")

    print("", flush=True)
    print("  Wiki endpoints:")
    print("    GET  /api/v1/wiki/scopes   list the wikis you can read")
    print("    POST /api/v1/wiki/upload   add raw sources; the agent ingests them")

    if settings.agent_bin_path is None:
        print("", flush=True)
        print(f"  note: no opencode binary at {settings.wiki.agent_bin}, so")
        print("        ingest and query runs will fail. Set SELFMEMORY_AGENT_BIN.")
    elif not settings.agent_has_credentials:
        print("", flush=True)
        print("  note: the opencode agent has no model credentials, so runs will")
        print("        fail. Set ANTHROPIC_API_KEY (or another *_API_KEY) or log")
        print(f"        in to opencode with HOME={settings.wiki.agent_home}.")

    print("", flush=True)
    print("  Ctrl-C stops the API. Mongo stays up; `make stop` clears it.")
    print("=" * 64, flush=True)
