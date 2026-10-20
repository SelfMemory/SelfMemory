"""Tests for workspace materialization and the agent session adapter.

No subprocess and no network: the agent runtime is a fake, so what is under
test is the projection, the read-back, the isolation rules and the citation
handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from selfmemory.knowledge import (
    KnowledgeMemory,
    Page,
    SQLiteKnowledgeStore,
    Workspace,
)
from selfmemory.knowledge.session import (
    AgentSessionError,
    OpencodeRunner,
    SessionResult,
    _last_text,
    extract_citations,
)
from selfmemory.knowledge.workspace import (
    markdown_to_page,
    page_to_markdown,
    render_index,
)


class FakeRunner:
    """Records the directory it was pointed at and returns a canned answer."""

    def __init__(self, text="answered", edits=None):
        self.text = text
        self.edits = edits or {}
        self.calls: list[dict] = []

    def run(self, cwd, prompt, *, writable=False, timeout=180):
        self.calls.append({"cwd": Path(cwd), "prompt": prompt, "writable": writable})
        for rel, body in self.edits.items():
            path = Path(cwd) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        return SessionResult(text=self.text)


@pytest.fixture
def store():
    s = SQLiteKnowledgeStore(":memory:")
    s.apply(
        "acme",
        [
            (
                Page(
                    slug="topic/tooling",
                    title="Tooling",
                    body="Uses uv. See [[project/selfmemory]].",
                    frontmatter={"summary": "Build tooling"},
                ),
                None,
            ),
            (
                Page(
                    slug="project/selfmemory",
                    title="selfmemory",
                    body="A memory backend.",
                    frontmatter={"summary": "The product"},
                ),
                None,
            ),
        ],
        [],
    )
    s.apply(
        "payroll",
        [(Page(slug="salaries", title="Salaries", body="Secret figures."), None)],
        [],
    )
    return s


# -- materialization ---------------------------------------------------


def test_pages_are_written_as_markdown_files(store):
    with Workspace.materialize(store, ["acme"]) as ws:
        text = (ws.session_root / "pages" / "topic" / "tooling.md").read_text()
        assert "Uses uv." in text
        assert "summary: Build tooling" in text
        assert (ws.session_root / "index.md").exists()
        assert (ws.session_root / "schema.md").exists()


def test_index_lists_every_page(store):
    with Workspace.materialize(store, ["acme"]) as ws:
        index = (ws.session_root / "index.md").read_text()
        assert "topic/tooling" in index
        assert "project/selfmemory" in index


def test_single_project_is_rooted_at_that_project(store):
    with Workspace.materialize(store, ["acme"]) as ws:
        assert ws.session_root == ws.root / "acme"


def test_multi_project_is_rooted_above_both(store):
    with Workspace.materialize(store, ["acme", "payroll"]) as ws:
        assert ws.session_root == ws.root
        assert (ws.root / "acme").is_dir()
        assert (ws.root / "payroll").is_dir()


def test_only_requested_projects_are_materialized(store):
    """The isolation guarantee: excluded data is absent, not filtered."""
    with Workspace.materialize(store, ["acme"]) as ws:
        assert not (ws.root / "payroll").exists()
        assert "Secret figures" not in _read_all(ws.root)


def test_workspace_is_wiped_on_exit(store):
    with Workspace.materialize(store, ["acme"]) as ws:
        root = ws.root
        assert root.exists()
    assert not root.exists()


def test_read_only_workspace_disables_write_tools(store):
    with Workspace.materialize(store, ["acme"], writable=False) as ws:
        config = (ws.session_root / "opencode.json").read_text()
        assert '"write": false' in config
        assert '"bash": false' in config


def test_writable_workspace_gets_no_restriction_file(store):
    with Workspace.materialize(store, ["acme"], writable=True) as ws:
        assert not (ws.session_root / "opencode.json").exists()


def test_writable_multi_project_is_refused(store):
    """The invariant that stops one project exfiltrating another."""
    with pytest.raises(ValueError, match="exactly one project"):
        Workspace.materialize(store, ["acme", "payroll"], writable=True)


def test_empty_project_list_is_refused(store):
    with pytest.raises(ValueError):
        Workspace.materialize(store, [])


def test_empty_project_still_materializes(store):
    with Workspace.materialize(store, ["brand-new"]) as ws:
        assert "No pages yet" in (ws.session_root / "index.md").read_text()


# -- read back ---------------------------------------------------------


def test_untouched_pages_are_not_reported_as_changed(store):
    with Workspace.materialize(store, ["acme"], writable=True) as ws:
        assert ws.changed_pages() == []


def test_an_edited_page_comes_back(store):
    with Workspace.materialize(store, ["acme"], writable=True) as ws:
        path = ws.page_path("acme", "topic/tooling")
        path.write_text(
            "---\nsummary: now ruff too\n---\n\n# Tooling\n\nUses uv and ruff.",
            encoding="utf-8",
        )
        changed = ws.changed_pages()

    assert len(changed) == 1
    assert changed[0].slug == "topic/tooling"
    assert changed[0].body == "Uses uv and ruff."
    assert changed[0].summary == "now ruff too"


def test_a_new_page_comes_back(store):
    with Workspace.materialize(store, ["acme"], writable=True) as ws:
        path = ws.page_path("acme", "person/shrijayan")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Shrijayan\n\nBased in Chennai.", encoding="utf-8")
        changed = ws.changed_pages()

    assert [p.slug for p in changed] == ["person/shrijayan"]
    assert changed[0].title == "Shrijayan"


def test_a_removed_page_is_reported(store):
    with Workspace.materialize(store, ["acme"], writable=True) as ws:
        ws.page_path("acme", "topic/tooling").unlink()
        assert ws.deleted_slugs() == ["topic/tooling"]


def test_roundtrip_preserves_content(store):
    page = Page(
        slug="a/b",
        title="A B",
        body="Body with [[link]].",
        frontmatter={"summary": "s", "sources": ["x1"]},
    )
    back = markdown_to_page("a/b", page_to_markdown(page))

    assert back.title == page.title
    assert back.body == page.body
    assert back.summary == "s"
    assert back.frontmatter["sources"] == ["x1"]


def test_page_without_frontmatter_still_parses():
    page = markdown_to_page("a", "# Title\n\nJust a body.")
    assert page.title == "Title"
    assert page.body == "Just a body."


def test_page_with_broken_frontmatter_keeps_its_body():
    page = markdown_to_page("a", "---\n:::not yaml:::\n---\n\n# T\n\nBody.")
    assert "Body." in page.body


def test_render_index_of_nothing():
    assert "No pages yet" in render_index([])


# -- citations ---------------------------------------------------------


def test_citations_are_extracted_from_links_and_paths():
    known = {"topic/tooling", "project/selfmemory"}
    text = "They use uv [[topic/tooling]], per `project/selfmemory.md`."
    assert extract_citations(text, known) == ["topic/tooling", "project/selfmemory"]


def test_hallucinated_citations_are_dropped():
    assert extract_citations("see [[no/such/page]]", {"real"}) == []


def test_citations_are_deduplicated():
    text = "[[a]] and again [[a]]"
    assert extract_citations(text, {"a"}) == ["a"]


def test_pages_prefix_is_tolerated():
    assert extract_citations("`pages/a.md`", {"a"}) == ["a"]


# -- runner ------------------------------------------------------------


def test_missing_binary_raises_rather_than_returning_nothing():
    runner = OpencodeRunner(binary="definitely-not-installed-xyz")
    assert not runner.available()
    with pytest.raises(AgentSessionError, match="not on PATH"):
        runner.run(Path("/tmp"), "hi", writable=False, timeout=1)


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        (
            '{"type":"text","part":{"type":"text","text":"one"}}\n'
            '{"type":"text","part":{"type":"text","text":"two"}}',
            "two",
        ),
        (
            '{"type":"tool_use","part":{"type":"tool","state":{"output":"junk"}}}\n'
            '{"type":"text","part":{"type":"text","text":"the answer"}}',
            "the answer",
        ),
        ('{"text": "one"}\n{"text": "two"}', "two"),
        ('{"message": "hello"}', "hello"),
        ('{"output": "single object"}', "single object"),
        ("not json at all", "not json at all"),
        ('garbage\n{"text": "recovered"}', "recovered"),
    ],
)
def test_last_text_survives_stream_shape_changes(stdout, expected):
    assert _last_text(stdout) == expected


# -- research ----------------------------------------------------------


def test_research_points_the_agent_at_the_project(store):
    runner = FakeRunner(text="They use uv [[topic/tooling]].")
    mem = KnowledgeMemory(store=store, llm=None, runner=runner, project_id="acme")
    answer = mem.research("what tooling?")

    assert answer.citations == ["topic/tooling"]
    assert runner.calls[0]["writable"] is False
    assert runner.calls[0]["cwd"].name == "acme"


def test_research_never_materializes_an_unlisted_project(store):
    captured = {}

    class Peeking(FakeRunner):
        def run(self, cwd, prompt, **kw):
            captured["contents"] = _read_all(Path(cwd).parent)
            return super().run(cwd, prompt, **kw)

    mem = KnowledgeMemory(store=store, llm=None, runner=Peeking(), project_id="acme")
    mem.research("anything")
    assert "Secret figures" not in captured["contents"]


def test_research_cleans_up_even_when_the_agent_fails(store):
    seen = {}

    class Failing:
        def run(self, cwd, prompt, **kw):
            seen["root"] = Path(cwd).parent
            raise AgentSessionError("boom")

    mem = KnowledgeMemory(store=store, llm=None, runner=Failing(), project_id="acme")
    with pytest.raises(AgentSessionError):
        mem.research("anything")
    assert not seen["root"].exists()


def test_research_spans_several_projects(store):
    runner = FakeRunner(text="see [[salaries]] and [[topic/tooling]]")
    mem = KnowledgeMemory(store=store, llm=None, runner=runner, project_id="acme")
    answer = mem.research("across", project_ids=["acme", "payroll"])

    assert set(answer.citations) == {"salaries", "topic/tooling"}
    assert runner.calls[0]["cwd"] == runner.calls[0]["cwd"]


def _read_all(root: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in root.rglob("*.md") if p.is_file()
    )
