"""Tests for the local development stack manager.

The waiting and config code is where this kind of script actually goes wrong,
so it is tested rather than exercised by hand. The subprocess-spawning paths
are deliberately not tested here: they are thin wrappers over docker and
uvicorn, and a test that shells out to a real daemon verifies that docker
works, not that this code is correct.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

import selfmemory.platform.sandbox.isolation as isolation
from scripts.devstack import lifecycle, waiters
from scripts.devstack.settings import ConfigError, Settings, load_settings, require
from selfmemory.wiki_settings import DEFAULT_AGENT_ENV, WikiSettings

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


@pytest.fixture
def free_port() -> int:
    """Return a port with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def listener(free_port: int):
    """Start a throwaway TCP listener and yield (host, port)."""
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", free_port))
    server.listen(5)
    yield ("127.0.0.1", free_port)
    server.close()


def make_wiki(tmp: Path, **overrides) -> WikiSettings:
    """A WikiSettings rooted in ``tmp`` with no reachable agent by default."""
    base = {
        "data_root": tmp / "data",
        "agent_home": tmp / "data" / ".agent",
        "agent_bin": str(tmp / "no-such-opencode"),
    }
    base.update(overrides)
    return WikiSettings(**base)


def make_settings(tmp: Path | None = None, **overrides) -> Settings:
    """Build a Settings with local-only defaults, overridable per test."""
    tmp = tmp or Path("/nonexistent-devstack-test")
    base = {
        "api_host": "127.0.0.1",
        "api_port": 8081,
        "api_reload": False,
        "mongo_port": 27017,
        "mongo_uri": "mongodb://127.0.0.1:27017/selfmemory",
        "wiki": make_wiki(tmp),
        "start_timeout": 5.0,
        "strict_port": False,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def no_agent_keys(monkeypatch):
    """Clear every *_API_KEY the agent allowlist would accept."""
    for name in DEFAULT_AGENT_ENV:
        if name.endswith("_API_KEY"):
            monkeypatch.delenv(name, raising=False)


def _fake_report(**fields):
    report = {"kind": None, "ok": False, "blocked": False, "detail": ""}
    report.update(fields)
    return lambda settings: report


# --------------------------------------------------------------------------
# waiters
# --------------------------------------------------------------------------


class TestWaitForPort:
    def test_returns_true_once_something_is_listening(self, listener):
        host, port = listener
        assert waiters.wait_for_port(host, port, timeout=2) is True

    def test_raises_with_the_address_in_the_message(self, free_port):
        with pytest.raises(TimeoutError) as exc:
            waiters.wait_for_port(
                "127.0.0.1", free_port, timeout=0.3, poll_interval=0.1
            )

        assert str(free_port) in str(exc.value)

    def test_succeeds_when_the_service_appears_late(self, free_port):
        """A container that takes a moment to bind must not be a hard failure."""
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        def open_later() -> None:
            threading.Event().wait(0.4)
            server.bind(("127.0.0.1", free_port))
            server.listen(5)
            threading.Event().wait(3)

        thread = threading.Thread(target=open_later, daemon=True)
        thread.start()
        try:
            assert waiters.wait_for_port(
                "127.0.0.1", free_port, timeout=5, poll_interval=0.1
            )
        finally:
            server.close()
            thread.join(timeout=1)


class TestWaitForHttpIdentityCheck:
    """A 200 from the wrong service is not readiness.

    Found in practice: an unrelated React app ("Temps") was holding :8081 and
    answered 200 with HTML, which a status-code-only probe reported as a
    healthy SelfMemory API while the real server was never started.
    """

    def _serve(self, port: int, body: bytes, content_type: str):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_rejects_html_from_a_foreign_server(self, free_port):
        server = self._serve(
            free_port, b"<!DOCTYPE html><title>Temps</title>", "text/html"
        )
        try:
            with pytest.raises(TimeoutError) as exc:
                waiters.wait_for_http(
                    f"http://127.0.0.1:{free_port}/health",
                    timeout=0.5,
                    poll_interval=0.1,
                    expect_json_keys=("status", "checks"),
                )
            assert "missing" in str(exc.value)
        finally:
            server.shutdown()

    def test_accepts_the_real_health_payload(self, free_port):
        server = self._serve(
            free_port,
            b'{"status": "healthy", "checks": {"database": {"status": "healthy"}}}',
            "application/json",
        )
        try:
            assert waiters.wait_for_http(
                f"http://127.0.0.1:{free_port}/health",
                timeout=2,
                poll_interval=0.1,
                expect_json_keys=("status", "checks"),
            )
        finally:
            server.shutdown()

    def test_rejects_json_that_is_missing_a_key(self, free_port):
        server = self._serve(free_port, b'{"ok": true}', "application/json")
        try:
            with pytest.raises(TimeoutError):
                waiters.wait_for_http(
                    f"http://127.0.0.1:{free_port}/health",
                    timeout=0.5,
                    poll_interval=0.1,
                    expect_json_keys=("status", "checks"),
                )
        finally:
            server.shutdown()

    def test_rejects_json_that_is_not_an_object(self, free_port):
        server = self._serve(free_port, b"[1, 2, 3]", "application/json")
        try:
            with pytest.raises(TimeoutError):
                waiters.wait_for_http(
                    f"http://127.0.0.1:{free_port}/health",
                    timeout=0.5,
                    poll_interval=0.1,
                    expect_json_keys=("status",),
                )
        finally:
            server.shutdown()

    def test_no_expectation_means_status_code_only(self, free_port):
        """Opt-in, so existing callers keep their simpler behaviour."""
        server = self._serve(free_port, b"anything", "text/plain")
        try:
            assert waiters.wait_for_http(
                f"http://127.0.0.1:{free_port}/health", timeout=2, poll_interval=0.1
            )
        finally:
            server.shutdown()


class TestHealthPayloadKeys:
    def test_keys_match_what_the_server_returns(self):
        """Guard against the app's health shape changing under us."""
        assert "status" in lifecycle.HEALTH_PAYLOAD_KEYS
        assert "checks" in lifecycle.HEALTH_PAYLOAD_KEYS


class TestWaitForHttp:
    def test_surfaces_the_body_when_the_status_never_matches(self, free_port):
        """A 503 saying WHICH dependency is down is the whole value here."""
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                payload = b'{"status": "unhealthy", "database": "down"}'
                self.send_response(503)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", port := free_port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with pytest.raises(TimeoutError) as exc:
                waiters.wait_for_http(
                    f"http://127.0.0.1:{port}/health", timeout=0.5, poll_interval=0.1
                )
            assert "database" in str(exc.value)
        finally:
            server.shutdown()


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------


class TestRequire:
    def test_returns_the_value_when_present(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "  spaced  ")
        assert require("SOME_VAR", "set it") == "spaced"

    def test_raises_with_the_hint_when_absent(self, monkeypatch):
        monkeypatch.delenv("SOME_VAR", raising=False)
        with pytest.raises(ConfigError) as exc:
            require("SOME_VAR", "put it in .env")
        assert "put it in .env" in str(exc.value)

    def test_treats_whitespace_as_absent(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "   ")
        with pytest.raises(ConfigError):
            require("SOME_VAR", "hint")


class TestLoadSettings:
    def test_reads_ports_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("SELFMEMORY_SERVER_PORT", "9999")
        monkeypatch.setenv("MONGODB_PORT", "27018")
        settings = load_settings(env_file=Path("/nonexistent"))

        assert settings.api_port == 9999
        assert settings.mongo_port == 27018

    def test_rejects_a_non_numeric_port_instead_of_crashing_later(self, monkeypatch):
        """A typo in a port should name the variable, not surface as a bind error."""
        monkeypatch.setenv("MONGODB_PORT", "not-a-port")
        with pytest.raises(ConfigError) as exc:
            load_settings(env_file=Path("/nonexistent"))
        assert "MONGODB_PORT" in str(exc.value)

    def test_existing_environment_beats_the_env_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SELFMEMORY_SERVER_PORT", "1111")
        env_file = tmp_path / ".env"
        env_file.write_text("SELFMEMORY_SERVER_PORT=2222\n")

        assert load_settings(env_file=env_file).api_port == 1111

    def test_values_from_the_env_file_are_used_when_not_in_the_environment(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv("MONGODB_PORT", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("MONGODB_PORT=27019\n")

        assert load_settings(env_file=env_file).mongo_port == 27019


class TestFlagParsing:
    """Flags accept 1/true/yes/on, matching selfmemory.wiki_settings.

    Regression: DEVSTACK_STRICT_PORT=1 used to read as off, because only the
    literal string "true" was accepted.
    """

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On", " on "])
    def test_strict_port_accepts_truthy_spellings(self, monkeypatch, value):
        monkeypatch.setenv("DEVSTACK_STRICT_PORT", value)
        assert load_settings(env_file=Path("/nonexistent")).strict_port is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "nonsense"])
    def test_strict_port_rejects_other_values(self, monkeypatch, value):
        monkeypatch.setenv("DEVSTACK_STRICT_PORT", value)
        assert load_settings(env_file=Path("/nonexistent")).strict_port is False

    def test_strict_port_defaults_off(self, monkeypatch):
        monkeypatch.delenv("DEVSTACK_STRICT_PORT", raising=False)
        assert load_settings(env_file=Path("/nonexistent")).strict_port is False

    @pytest.mark.parametrize("value", ["1", "yes", "on", "true"])
    def test_api_reload_accepts_truthy_spellings(self, monkeypatch, value):
        monkeypatch.setenv("API_RELOAD", value)
        assert load_settings(env_file=Path("/nonexistent")).api_reload is True

    @pytest.mark.parametrize("value", ["0", "no", "off", "false"])
    def test_api_reload_can_be_turned_off(self, monkeypatch, value):
        monkeypatch.setenv("API_RELOAD", value)
        assert load_settings(env_file=Path("/nonexistent")).api_reload is False

    def test_api_reload_defaults_on(self, monkeypatch):
        monkeypatch.delenv("API_RELOAD", raising=False)
        assert load_settings(env_file=Path("/nonexistent")).api_reload is True


class TestWikiSettingsWiring:
    def test_data_root_comes_from_the_environment(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SELFMEMORY_DATA_ROOT", str(tmp_path / "root"))
        settings = load_settings(env_file=Path("/nonexistent"))
        assert settings.wiki.data_root == tmp_path / "root"

    def test_data_root_is_read_from_the_env_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SELFMEMORY_DATA_ROOT", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(f"SELFMEMORY_DATA_ROOT={tmp_path / 'from-file'}\n")
        try:
            settings = load_settings(env_file=env_file)
            assert settings.wiki.data_root == tmp_path / "from-file"
        finally:
            # load_dotenv writes into os.environ; do not leak into other tests.
            monkeypatch.delenv("SELFMEMORY_DATA_ROOT", raising=False)


class TestDescribeWiki:
    def test_reports_absent_when_the_data_root_does_not_exist(self, tmp_path):
        described = make_settings(tmp_path).describe_wiki()
        assert str(tmp_path / "data") in described
        assert "absent" in described

    def test_counts_zero_orgs_when_orgs_dir_is_missing(self, tmp_path):
        (tmp_path / "data").mkdir()
        described = make_settings(tmp_path).describe_wiki()
        assert "0 orgs" in described
        assert "absent" not in described

    def test_counts_org_directories_only(self, tmp_path):
        orgs = tmp_path / "data" / "orgs"
        for name in ("acme", "globex"):
            (orgs / name / "wiki").mkdir(parents=True)
        (orgs / "stray-file.txt").write_text("not an org")
        assert "2 orgs" in make_settings(tmp_path).describe_wiki()

    def test_singular_for_one_org(self, tmp_path):
        (tmp_path / "data" / "orgs" / "acme").mkdir(parents=True)
        assert "(1 org)" in make_settings(tmp_path).describe_wiki()

    def test_never_creates_the_data_root(self, tmp_path):
        """Describing must not have side effects on disk."""
        make_settings(tmp_path).describe_wiki()
        assert not (tmp_path / "data").exists()


class TestAgentReadiness:
    @staticmethod
    def _binary(tmp_path: Path) -> Path:
        binary = tmp_path / "opencode"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        return binary

    def test_missing_binary_is_not_ready(self, tmp_path, monkeypatch, no_agent_keys):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        settings = make_settings(tmp_path)
        assert settings.agent_bin_path is None
        assert settings.agent_has_credentials is True
        assert settings.agent_ready is False

    def test_binary_without_credentials_is_not_ready(self, tmp_path, no_agent_keys):
        wiki = make_wiki(tmp_path, agent_bin=str(self._binary(tmp_path)))
        settings = make_settings(tmp_path, wiki=wiki)
        assert settings.agent_bin_path is not None
        assert settings.agent_has_credentials is False
        assert settings.agent_ready is False

    def test_binary_plus_api_key_is_ready(self, tmp_path, monkeypatch, no_agent_keys):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
        wiki = make_wiki(tmp_path, agent_bin=str(self._binary(tmp_path)))
        settings = make_settings(tmp_path, wiki=wiki)
        assert settings.agent_key_env == ["OPENROUTER_API_KEY"]
        assert settings.agent_ready is True

    def test_binary_plus_auth_json_is_ready(self, tmp_path, no_agent_keys):
        wiki = make_wiki(tmp_path, agent_bin=str(self._binary(tmp_path)))
        settings = make_settings(tmp_path, wiki=wiki)
        settings.agent_auth_file.parent.mkdir(parents=True)
        settings.agent_auth_file.write_text("{}")
        assert settings.agent_ready is True
        assert str(settings.agent_auth_file) in settings.describe_agent()

    def test_whitespace_key_is_not_a_credential(
        self, tmp_path, monkeypatch, no_agent_keys
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
        assert make_settings(tmp_path).agent_has_credentials is False

    def test_only_allowlisted_keys_count(self, tmp_path, monkeypatch, no_agent_keys):
        """A key the agent is never handed cannot authenticate it."""
        monkeypatch.setenv("SOME_VENDOR_API_KEY", "x")
        assert make_settings(tmp_path).agent_has_credentials is False

    def test_bare_binary_name_is_resolved_on_path(
        self, tmp_path, monkeypatch, no_agent_keys
    ):
        self._binary(tmp_path)
        monkeypatch.setenv("PATH", str(tmp_path))
        wiki = make_wiki(tmp_path, agent_bin="opencode")
        settings = make_settings(tmp_path, wiki=wiki)
        assert settings.agent_bin_path == str(tmp_path / "opencode")

    def test_describe_agent_names_what_is_missing(self, tmp_path, no_agent_keys):
        described = make_settings(tmp_path).describe_agent()
        assert "missing" in described
        assert "NO credentials" in described


class TestApiPortFallback:
    """`make run` must not die because an unrelated app holds the port.

    Found in practice: an unrelated app ("temps") held :8081, so every `make
    run` failed. Failing is correct behaviour only when something downstream
    depends on the exact port, which DEVSTACK_STRICT_PORT opts into.
    """

    def test_keeps_the_configured_port_when_it_is_free(self, free_port):
        settings = make_settings(api_port=free_port)
        assert lifecycle._resolve_api_port(settings) == free_port

    def test_moves_to_the_next_free_port_when_occupied(self, listener):
        _, occupied = listener
        chosen = lifecycle._resolve_api_port(make_settings(api_port=occupied))

        assert chosen != occupied
        assert not lifecycle.port_in_use("127.0.0.1", chosen)

    def test_picks_a_port_above_the_configured_one(self, listener):
        _, occupied = listener
        chosen = lifecycle._resolve_api_port(make_settings(api_port=occupied))
        assert chosen > occupied

    def test_strict_mode_refuses_to_move(self, listener):
        _, occupied = listener
        settings = make_settings(api_port=occupied, strict_port=True)
        with pytest.raises(lifecycle.PreflightError):
            lifecycle._check_api_port(settings)

    def test_strict_mode_message_names_the_holder_and_the_way_out(self, listener):
        _, occupied = listener
        with pytest.raises(lifecycle.PreflightError) as exc:
            lifecycle._check_api_port(
                make_settings(api_port=occupied, strict_port=True)
            )

        assert str(occupied) in str(exc.value)
        assert "lsof" in str(exc.value)

    def test_fails_when_no_port_is_free_in_the_window(self, monkeypatch):
        """Exhausting the scan must say so rather than picking a bound port."""
        monkeypatch.setattr(lifecycle, "port_in_use", lambda *a, **k: True)
        with pytest.raises(lifecycle.PreflightError):
            lifecycle._check_api_port(make_settings(api_port=8081, strict_port=False))

    def test_next_free_port_returns_none_when_the_window_is_full(self, monkeypatch):
        monkeypatch.setattr(lifecycle, "port_in_use", lambda *a, **k: True)
        assert lifecycle._next_free_port(8081) is None

    def test_scan_window_is_bounded(self, monkeypatch):
        """Bound the scan so a fully-occupied range cannot hang startup."""
        monkeypatch.setattr(lifecycle, "port_in_use", lambda *a, **k: True)
        with pytest.raises(lifecycle.PreflightError):
            lifecycle._check_api_port(make_settings(api_port=8081))

    def test_status_and_up_resolve_the_same_port(self, listener):
        """Regression: status reported a different URL than the running server."""
        _, occupied = listener
        settings = make_settings(api_port=occupied)
        assert lifecycle._resolve_api_port(settings) == lifecycle._resolve_api_port(
            settings
        )


class TestFindRunningApiPort:
    """`status` must find the API by identity, not by guessing the port.

    Regression: `up` had moved the API to 8082, `status` then scanned past it,
    treated the running server as just another occupied port, and reported 8083.
    """

    def _serve_health(
        self, port: int, body: bytes, content_type: str = "application/json"
    ):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_finds_a_healthy_api_on_the_fallback_port(self, free_port):
        """The real case: configured port taken, API one above it."""
        occupied = socket.socket()
        occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupied.bind(("127.0.0.1", free_port))
        occupied.listen(1)
        target = free_port + 1
        server = self._serve_health(target, b'{"status":"healthy","checks":{}}')
        try:
            found = lifecycle.find_running_api_port(make_settings(api_port=free_port))
            assert found == target
        finally:
            server.shutdown()
            occupied.close()

    def test_returns_none_when_nothing_is_serving(self, free_port):
        assert (
            lifecycle.find_running_api_port(make_settings(api_port=free_port)) is None
        )

    def test_ignores_a_foreign_server_on_the_configured_port(self, free_port):
        """Something else answering 200 must not be reported as the API."""
        server = self._serve_health(
            free_port, b"<!DOCTYPE html><title>Temps</title>", "text/html"
        )
        try:
            assert (
                lifecycle.find_running_api_port(make_settings(api_port=free_port))
                is None
            )
        finally:
            server.shutdown()

    def test_prefers_the_configured_port_when_it_is_ours(self, free_port):
        server = self._serve_health(free_port, b'{"status":"healthy","checks":{}}')
        try:
            assert (
                lifecycle.find_running_api_port(make_settings(api_port=free_port))
                == free_port
            )
        finally:
            server.shutdown()

    def test_scan_is_bounded(self, monkeypatch):
        """An all-occupied range must not turn status into a long wait."""
        monkeypatch.setattr(lifecycle, "port_in_use", lambda *a, **k: True)
        monkeypatch.setattr(lifecycle, "api_already_serving", lambda s: False)
        assert lifecycle.find_running_api_port(make_settings(api_port=8081)) is None


class TestChildEnv:
    def test_passes_the_environment_through(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-123")
        monkeypatch.setenv("SELFMEMORY_DATA_ROOT", "/somewhere")
        env = lifecycle._child_env(make_settings())
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-123"
        assert env["SELFMEMORY_DATA_ROOT"] == "/somewhere"

    def test_does_not_mutate_the_parent_environment(self, monkeypatch):
        import os

        monkeypatch.setenv("SELFMEMORY_DATA_ROOT", "/somewhere")
        env = lifecycle._child_env(make_settings())
        env["SELFMEMORY_DATA_ROOT"] = "/elsewhere"
        assert os.environ["SELFMEMORY_DATA_ROOT"] == "/somewhere"


class TestServiceDescription:
    def test_lists_api_and_mongodb(self):
        names = [name for name, _, _ in make_settings().describe_services()]
        assert names == ["api", "mongodb"]

    def test_lists_only_probeable_things(self):
        """The wiki is a directory; probing it as a service would break."""
        names = [name for name, _, _ in make_settings().describe_services()]
        assert "wiki" not in names

    def test_never_lists_a_vector_store_or_embedder(self):
        names = " ".join(name for name, _, _ in make_settings().describe_services())
        assert "qdrant" not in names.lower()
        assert "ollama" not in names.lower()


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------


class TestCheckConfig:
    def test_warns_about_a_missing_agent_and_credentials(
        self, tmp_path, capsys, no_agent_keys
    ):
        lifecycle.check_config(make_settings(tmp_path))
        out = capsys.readouterr().out
        assert "opencode agent binary not found" in out
        assert "no model credentials" in out

    def test_quiet_about_the_agent_when_it_is_ready(
        self, tmp_path, monkeypatch, capsys, no_agent_keys
    ):
        binary = tmp_path / "opencode"
        binary.write_text("")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        wiki = make_wiki(tmp_path, agent_bin=str(binary))
        lifecycle.check_config(make_settings(tmp_path, wiki=wiki))
        out = capsys.readouterr().out
        assert "opencode" not in out
        assert "credentials" not in out


class TestStatus:
    def test_prints_wiki_agent_and_isolation_rows(
        self, tmp_path, monkeypatch, capsys, free_port, no_agent_keys
    ):
        monkeypatch.setattr(isolation, "isolation_report", _fake_report())
        monkeypatch.setattr(lifecycle, "find_running_api_port", lambda s: None)
        settings = make_settings(tmp_path, api_port=free_port, mongo_port=free_port)

        assert lifecycle.status(settings) == 0
        out = capsys.readouterr().out
        assert "wiki" in out and "absent" in out
        assert "NOT READY" in out
        assert "unconfined" in out
        assert "knowledge" not in out

    def test_reports_a_confined_kind(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            isolation, "isolation_report", _fake_report(kind="bwrap", ok=True)
        )
        line = lifecycle._isolation_summary(make_settings(tmp_path))
        assert line.split()[:2] == ["ok", "bwrap"]

    def test_reports_a_blocked_isolation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            isolation,
            "isolation_report",
            _fake_report(blocked=True, detail="no sandbox"),
        )
        line = lifecycle._isolation_summary(make_settings(tmp_path))
        assert "BLOCKED" in line
        assert "no sandbox" in line

    def test_survives_a_failing_isolation_probe(self, tmp_path, monkeypatch):
        def boom(settings):
            raise RuntimeError("docker exploded")

        monkeypatch.setattr(isolation, "isolation_report", boom)
        line = lifecycle._isolation_summary(make_settings(tmp_path))
        assert "docker exploded" in line


class TestPrintReady:
    def test_points_at_the_wiki_endpoints(self, tmp_path, capsys, no_agent_keys):
        lifecycle._print_ready(make_settings(tmp_path))
        out = capsys.readouterr().out
        assert "/api/v1/wiki/scopes" in out
        assert "/api/v1/wiki/upload" in out
        assert "dev_seed_api_key" in out
        assert "/api/knowledge" not in out

    def test_warns_when_the_agent_cannot_run(self, tmp_path, capsys, no_agent_keys):
        lifecycle._print_ready(make_settings(tmp_path))
        assert "SELFMEMORY_AGENT_BIN" in capsys.readouterr().out


class TestProbeSummary:
    def test_reports_down_instead_of_raising(self, free_port):
        """status must always print a table, never blow up mid-report."""
        assert lifecycle._probe_summary("mongodb", f"127.0.0.1:{free_port}") == "down"
        assert (
            lifecycle._probe_summary("api", f"http://127.0.0.1:{free_port}") == "down"
        )

    def test_reports_up_for_a_listening_service(self, listener):
        host, port = listener
        assert lifecycle._probe_summary("mongodb", f"{host}:{port}") == "up"


class TestManagedServices:
    def test_only_mongodb_is_managed(self):
        """A regression guard: Qdrant and Ollama must not creep back in."""
        assert lifecycle.MANAGED_SERVICES == ("mongodb",)
