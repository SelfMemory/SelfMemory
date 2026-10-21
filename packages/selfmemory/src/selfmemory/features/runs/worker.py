"""The run worker: claims queued jobs and executes them as agent runs.

Runs inside the API process by default (``SELFMEMORY_WORKER=off`` disables
that) and standalone with ``python -m selfmemory.features.runs.worker``. Any number of
workers can share one queue: claiming is one atomic update, and every write a
worker makes afterwards is guarded on it still owning the job.

Shutdown contract: on stop, a worker claims nothing new and abandons its
in-flight runs (kills them, writes nothing). The jobs stay ``running`` with a
stale heartbeat, and the reaper hands them back to the queue.
"""

from __future__ import annotations

import hashlib
import logging
import os
import socket
import threading
import time
from datetime import timedelta
from typing import TYPE_CHECKING

from selfmemory.features.runs.adapters.opencode import (
    RunPlan,
    install_agent_config,
    kill_run,
    parse_event,
)
from selfmemory.features.runs.store import ScopeBusyError, now
from selfmemory.features.tenancy.access import (
    AccessDenied,
    Principal,
    resolve_org_access,
)
from selfmemory.features.wiki.adapters.files import remove_symlinks
from selfmemory.features.wiki.service import WikiService
from selfmemory.kernel.logging import sanitize_for_log
from selfmemory.kernel.safe_paths import safe_segment
from selfmemory.platform.sandbox.isolation import (
    IsolationUnavailableError,
    get_isolation,
    require_isolation,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["Worker", "execute_job"]

logger = logging.getLogger(__name__)

HEARTBEAT_S = 10.0
FLUSH_S = 0.12
FLUSH_EVENTS = 32
MAX_ANSWER = 2_000_000
MAX_STDERR = 64_000
MAX_TOOLS = 500
PRUNE_AFTER = timedelta(hours=24)


class _Sink:
    """Buffers events and flushes them in batches; stops once the job is lost."""

    def __init__(self, service: WikiService, job_id: str, worker_id: str):
        self.service, self.job_id, self.worker_id = service, job_id, worker_id
        self.buf: list[dict] = []
        self.lock = threading.Lock()
        self.last = time.monotonic()
        self.count = 0
        self.dropped = 0
        self.lost = False
        # Appends must land in seq order: the reader thread and the main loop
        # can both flush, and an SSE cursor that passes a gap never returns.
        self.flush_lock = threading.Lock()

    def emit(self, event: dict) -> None:
        with self.lock:
            if self.count >= 20_000:
                self.dropped += 1
                return
            self.count += 1
            self.buf.append(event)
            due = (
                len(self.buf) >= FLUSH_EVENTS or time.monotonic() - self.last > FLUSH_S
            )
        if due:
            self.flush()

    def flush(self) -> None:
        with self.flush_lock:
            with self.lock:
                batch, self.buf = self.buf, []
                self.last = time.monotonic()
            if (
                batch
                and not self.lost
                and self.service.jobs.append(self.job_id, self.worker_id, batch) is None
            ):
                self.lost = True


def _fail(service, job, worker_id, sink, message, status="failed") -> None:
    sink.emit({"kind": "error", "message": message})
    sink.flush()
    result = {
        "code": 1,
        "answer": "",
        "error": message,
        "tools": [],
        "tokens": {},
        "cost": 0,
    }
    _chat_turn(service, job, "", {"error": message}, None)
    service.jobs.finish(job["_id"], worker_id, status, result)


def _chat_turn(service, job, answer, meta, session_id) -> None:
    if job.get("chatId"):
        service.chats.add_assistant_turn(
            job["chatId"], answer, {"mode": job["command"], **meta}, session_id
        )


def _add_usage(total: dict, tokens: dict) -> None:
    for k, v in (tokens or {}).items():
        if isinstance(v, (int, float)):
            total[k] = total.get(k, 0) + v
        elif isinstance(v, dict):
            _add_usage(total.setdefault(k, {}), v)


def _run_home(settings, job: dict) -> Path:
    """HOME for this job's agent: one per (organization, credential owner)."""
    owner = job.get("owner") or job["userId"]
    digest = hashlib.sha256(owner.encode()).hexdigest()[:24]
    return settings.data_root / ".homes" / safe_segment(job["orgId"]) / digest


def _commit_subject(job: dict) -> str:
    files = job.get("files") or []
    if files:
        first = files[0].rsplit("/", 1)[-1]
        return first if len(files) == 1 else f"{first} +{len(files) - 1} more"
    return (job.get("displayText") or job.get("message") or "").splitlines()[0][:72]


def execute_job(
    service: WikiService, job: dict, worker_id: str, stop: threading.Event
) -> None:
    settings = service.settings
    sink = _Sink(service, job["_id"], worker_id)
    principal = Principal.from_doc(job["principal"])

    try:
        access = resolve_org_access(service.db, settings, principal, job["orgId"])
    except AccessDenied as e:
        _fail(
            service, job, worker_id, sink, f"this account can no longer run here: {e}"
        )
        return
    if job.get("cancelRequestedAt"):
        _fail(service, job, worker_id, sink, "stopped", status="cancelled")
        return
    try:
        plan_dirs = access.mount_plan(job["command"], job.get("scope"))
        status = require_isolation(settings)
    except AccessDenied as e:
        _fail(service, job, worker_id, sink, str(e))
        return
    except IsolationUnavailableError as e:
        _fail(service, job, worker_id, sink, str(e))
        return

    service.ensure_all(access)
    lease = None
    target = None
    if job["command"] == "ingest":
        target = access.scope(job["scope"])
        lease = service.lease(
            access,
            target,
            f"ingest:{job['userId']}",
            ttl_s=90,
            wait_s=5,
            max_hold_s=settings.run_timeout_s + 120,
        )
        try:
            lease.acquire()
        except ScopeBusyError:
            # another ingest is writing this scope; try again shortly
            service.jobs.requeue(job["_id"], worker_id)
            return

    try:
        _run(
            service,
            job,
            worker_id,
            stop,
            sink,
            access,
            plan_dirs,
            status,
            target,
            lease,
        )
    finally:
        if lease is not None:
            lease.release()


def _run(service, job, worker_id, stop, sink, access, plan_dirs, status, target, lease):
    settings = service.settings
    if job.get("attempts", 1) > 1:
        sink.emit({"kind": "attempt", "attempt": job["attempts"]})
    plan = RunPlan(
        command=job["command"],
        message=job.get("message") or "",
        org_root=access.root,
        read_dirs=plan_dirs["read_dirs"],
        write_dir=plan_dirs["write_dir"],
        mask_dirs=plan_dirs["mask_dirs"],
        session_id=job.get("sessionId"),
        actor=job["userId"],
        scope_labels=plan_dirs["labels"],
        home=_run_home(settings, job),
        run_id=job["_id"],
    )
    from selfmemory.features.runs.adapters.opencode import spawn_agent

    try:
        proc = spawn_agent(settings, status, plan)
    except (OSError, RuntimeError) as e:
        _fail(service, job, worker_id, sink, f"could not start the agent: {e}")
        return
    sink.emit(
        {
            "kind": "start",
            "scope": job.get("scope"),
            "isolation": status.kind or "unconfined",
            "isolated": status.kind is not None,
        }
    )

    answer: list[str] = []
    answer_len = 0
    tools: list[dict] = []
    tokens: dict = {}
    cost = 0.0
    session_id = job.get("sessionId")
    errors: list[str] = []
    stderr: list[str] = []
    truncated = False

    def read_stdout():
        nonlocal answer_len, cost, session_id, truncated
        for line in proc.stdout:  # type: ignore[union-attr]
            text = line.decode("utf-8", errors="replace")[:1_000_000]
            for ev in parse_event(text):
                kind = ev["kind"]
                if kind == "session":
                    if ev["session_id"] != session_id:
                        session_id = ev["session_id"]
                        sink.emit(ev)
                    continue
                if kind == "text":
                    if answer_len + len(ev["text"]) > MAX_ANSWER:
                        truncated = True
                        continue
                    answer.append(ev["text"])
                    answer_len += len(ev["text"])
                elif kind == "tool" and len(tools) < MAX_TOOLS:
                    tools.append({"tool": ev["tool"], "title": ev["title"]})
                elif kind == "usage":
                    _add_usage(tokens, ev.get("tokens") or {})
                    cost += float(ev.get("cost") or 0)
                elif kind == "error":
                    errors.append(ev["message"])
                sink.emit(ev)

    def read_stderr():
        size = 0
        for line in proc.stderr:  # type: ignore[union-attr]
            if size < MAX_STDERR:
                chunk = line.decode("utf-8", errors="replace")
                stderr.append(chunk)
                size += len(chunk)

    readers = [
        threading.Thread(target=read_stdout, daemon=True),
        threading.Thread(target=read_stderr, daemon=True),
    ]
    for t in readers:
        t.start()

    started = time.monotonic()
    outcome: str | None = None  # "lost" | "abandoned" | "cancelled" | "timeout"
    try:
        outcome = _monitor(service, job, worker_id, stop, sink, proc, lease, started)
    finally:
        # Whatever happened above -- including Mongo raising mid-heartbeat --
        # the agent must not outlive this function: the lease is released by
        # the caller, and an orphan would keep writing the scope.
        if outcome or proc.poll() is None:
            kill_run(proc)
        proc.wait()
        for t in readers:
            t.join(timeout=5)
    _finish_run(
        service,
        job,
        worker_id,
        sink,
        access,
        target,
        proc,
        outcome,
        answer,
        tools,
        tokens,
        cost,
        session_id,
        errors,
        stderr,
        truncated,
    )


def _monitor(service, job, worker_id, stop, sink, proc, lease, started) -> str | None:
    settings = service.settings
    last_beat = started
    while proc.poll() is None:
        time.sleep(0.25)
        if stop.is_set():
            return "abandoned"
        if time.monotonic() - started > settings.run_timeout_s:
            return "timeout"
        if time.monotonic() - last_beat >= HEARTBEAT_S:
            last_beat = time.monotonic()
            beat = service.jobs.heartbeat(job["_id"], worker_id)
            if beat is None or sink.lost:
                return "lost"
            if beat.get("cancelRequestedAt"):
                return "cancelled"
            if lease is not None and not lease.renew():
                return "timeout"
    return None


def _finish_run(
    service,
    job,
    worker_id,
    sink,
    access,
    target,
    proc,
    outcome,
    answer,
    tools,
    tokens,
    cost,
    session_id,
    errors,
    stderr,
    truncated,
) -> None:
    settings = service.settings
    if outcome in ("lost", "abandoned"):
        # someone else owns this job now (or will); write nothing
        logger.info("run %s %s", sanitize_for_log(job["_id"]), outcome)
        return

    code = proc.returncode
    error = None
    if outcome == "timeout":
        error = f"the run took longer than {settings.run_timeout_s}s and was stopped"
    elif outcome == "cancelled":
        error = "stopped"
    elif errors:
        error = errors[-1]
    elif code != 0:
        tail = "".join(stderr).strip().splitlines()[-3:]
        error = f"agent exited with {code}" + (f": {' | '.join(tail)}" if tail else "")
    if error and outcome:
        sink.emit({"kind": "error", "message": error})

    commit = None
    if job["command"] == "ingest" and target is not None:
        # A link the agent made could point into another scope; none survive.
        removed = remove_symlinks(access.abs(target.wiki_rel))
        if removed:
            sink.emit(
                {"kind": "notice", "message": f"removed {len(removed)} symlink(s)"}
            )
    if job["command"] == "ingest" and target is not None and not error:
        try:
            sha = service.commit(
                access,
                target,
                f"[{now():%Y-%m-%d}] ingest | {_commit_subject(job)}\n\nby {job['userId']}",
            )
            if sha:
                commit = {"sha": sha, "scope": target.key}
                sink.emit({"kind": "commit", **commit})
        except Exception as e:  # noqa: BLE001 - a failed commit must still finish the job
            error = f"the run finished but its changes could not be committed: {e}"
            sink.emit({"kind": "error", "message": error})

    if sink.dropped:
        sink.emit({"kind": "notice", "message": f"{sink.dropped} events were dropped"})
    sink.flush()

    answer_text = "".join(answer)
    meta = {
        "scope": job.get("scope"),
        "tools": tools,
        "tokens": tokens,
        "cost": cost,
        "commit": commit,
        "error": error,
        "truncated": truncated,
    }
    _chat_turn(service, job, answer_text, meta, session_id)
    final = "cancelled" if outcome == "cancelled" else ("failed" if error else "done")
    service.jobs.finish(
        job["_id"],
        worker_id,
        final,
        {
            "code": code,
            "answer": answer_text,
            "error": error,
            "tools": tools,
            "tokens": tokens,
            "cost": cost,
            "commit": commit,
            "session_id": session_id,
            "truncated": truncated,
            "dropped_events": sink.dropped,
        },
    )


class Worker:
    """Polls the queue and runs up to ``max_concurrent_runs`` jobs at once."""

    def __init__(
        self, service: WikiService, worker_id: str | None = None, idle_s: float = 0.5
    ):
        self.service = service
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.idle_s = idle_s
        self.stop_event = threading.Event()
        self.active: set[threading.Thread] = set()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            install_agent_config(self.service.settings)
        except OSError as e:
            logger.warning("could not install agent config: %s", e)
        self.thread = threading.Thread(
            target=self.loop, name="wiki-worker", daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def _run_job(self, job: dict) -> None:
        try:
            execute_job(self.service, job, self.worker_id, self.stop_event)
        except Exception:  # noqa: BLE001 - one bad job must not kill the worker
            logger.exception("run %s crashed", sanitize_for_log(job["_id"]))
            self.service.jobs.finish(
                job["_id"],
                self.worker_id,
                "failed",
                {
                    "code": 1,
                    "answer": "",
                    "error": "internal error",
                    "tools": [],
                    "tokens": {},
                    "cost": 0,
                },
            )

    def loop(self) -> None:
        settings = self.service.settings
        n = 0
        while not self.stop_event.is_set():
            n += 1
            try:
                if n % 40 == 1:
                    self.service.jobs.reap_stale()
                    self.service.jobs.prune_finished(now() - PRUNE_AFTER)
                if get_isolation(settings).blocked:
                    self.stop_event.wait(10)
                    continue
                self.active = {t for t in self.active if t.is_alive()}
                claimed = False
                while len(self.active) < settings.max_concurrent_runs:
                    job = self.service.jobs.claim(self.worker_id)
                    if not job:
                        break
                    claimed = True
                    t = threading.Thread(target=self._run_job, args=(job,), daemon=True)
                    self.active.add(t)
                    t.start()
                if not claimed:
                    self.stop_event.wait(self.idle_s)
            except Exception:  # noqa: BLE001 - e.g. Mongo briefly unreachable
                logger.exception("worker loop error")
                self.stop_event.wait(5)


def main() -> None:  # pragma: no cover - process entry point
    import signal

    from dotenv import load_dotenv

    load_dotenv()
    from selfmemory.features.runs.store import ensure_indexes
    from selfmemory.platform.mongo.database import mongo_db
    from selfmemory.wiki_settings import load_settings

    logging.basicConfig(level=logging.INFO)
    ensure_indexes(mongo_db)
    worker = Worker(WikiService(mongo_db, load_settings()))
    signal.signal(signal.SIGTERM, lambda *_: worker.stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stop_event.set())
    worker.start()
    while not worker.stop_event.is_set():
        time.sleep(1)
    worker.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
