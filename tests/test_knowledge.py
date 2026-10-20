"""Tests for knowledge-base memory.

The LLM is scripted so the suite runs offline and deterministically -- what is
under test is the store, the edit plumbing and the concurrency guard, not the
model.
"""

from __future__ import annotations

import json

import pytest

from selfmemory.knowledge import (
    ConcurrentEditError,
    KnowledgeMemory,
    Page,
    SQLiteKnowledgeStore,
)
from selfmemory.knowledge.json_utils import MalformedResponseError, parse_json_object
from selfmemory.knowledge.models import LogEntry, utcnow
from selfmemory.knowledge.store import _fts_query, slugify


class ScriptedLLM:
    """Returns queued responses in order and records the prompts it saw."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def generate_response(self, messages, **kwargs):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        nxt = self.responses.pop(0)
        return nxt if isinstance(nxt, str) else json.dumps(nxt)


def select(open_slugs=(), propose=()):
    return {"open": list(open_slugs), "propose": list(propose)}


def merge(*edits):
    return {"edits": list(edits)}


def edit(op, slug, body, title=None, summary="s", reason="r"):
    return {
        "op": op,
        "slug": slug,
        "title": title or slug,
        "summary": summary,
        "body": body,
        "reason": reason,
    }


@pytest.fixture
def store():
    return SQLiteKnowledgeStore(":memory:")


def make_memory(store, responses):
    llm = ScriptedLLM(responses)
    return KnowledgeMemory(store=store, llm=llm), llm


# -- ingest ------------------------------------------------------------


def test_first_source_creates_a_page(store):
    mem, _ = make_memory(
        store, [merge(edit("create", "topic-tooling", "Uses uv, never pip."))]
    )
    result = mem.remember("Shrijayan uses uv, never pip.")

    assert result.created == ["topic-tooling"]
    page = mem.page("topic-tooling")
    assert page is not None
    assert "uv" in page.body
    assert page.summary == "s"
    assert page.sources == [result.source_id]


def test_empty_base_skips_the_select_call(store):
    """With no index there is nothing to select against -- save the call."""
    mem, llm = make_memory(store, [merge(edit("create", "a", "first fact"))])
    mem.remember("first fact")
    assert len(llm.calls) == 1


def test_second_source_updates_rather_than_duplicates(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "Uses uv.")),
            select(open_slugs=["tooling"]),
            merge(edit("update", "tooling", "Uses uv and ruff.")),
        ],
    )
    mem.remember("uses uv")
    mem.remember("also uses ruff")

    assert [p.slug for p in mem.pages()] == ["tooling"]
    assert mem.page("tooling").body == "Uses uv and ruff."


def test_update_preserves_created_at_and_appends_source(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling"]),
            merge(edit("update", "tooling", "v2")),
        ],
    )
    first = mem.remember("a")
    created_at = mem.page("tooling").created_at
    second = mem.remember("b")

    page = mem.page("tooling")
    assert page.created_at == created_at
    assert page.sources == [first.source_id, second.source_id]


def test_noop_edit_writes_nothing(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling"]),
            merge(edit("noop", "tooling", "", reason="unrelated")),
        ],
    )
    mem.remember("a")
    mem.remember("unrelated")

    assert mem.page("tooling").body == "v1"
    assert any(e.op == "ingest.noop" for e in mem.log())


def test_empty_body_is_never_written(store):
    """A model returning an empty body must not blank an existing page."""
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling"]),
            merge(edit("update", "tooling", "   ")),
        ],
    )
    mem.remember("a")
    mem.remember("b")
    assert mem.page("tooling").body == "v1"


def test_op_is_corrected_against_reality(store):
    """'create' on a page that exists becomes an update, not a clobber."""
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling"]),
            merge(edit("create", "tooling", "v2")),
        ],
    )
    mem.remember("a")
    result = mem.remember("b")

    assert result.updated == ["tooling"]
    assert store.page_version("default", "tooling") == 2


def test_update_of_unselected_page_is_dropped(store):
    """The model may not rewrite a page it was never shown."""
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=[]),
            merge(edit("update", "tooling", "clobbered")),
        ],
    )
    mem.remember("a")
    result = mem.remember("b")

    assert result.edits == []
    assert mem.page("tooling").body == "v1"


def test_select_ignores_hallucinated_slugs(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling", "does-not-exist"]),
            merge(edit("update", "tooling", "v2")),
        ],
    )
    mem.remember("a")
    result = mem.remember("b")
    assert result.pages_considered == ["tooling"]


def test_source_is_stored_immutably(store):
    mem, _ = make_memory(store, [merge(edit("create", "a", "b"))])
    result = mem.remember("raw text", metadata={"kind": "note"})

    source = store.get_source("default", result.source_id)
    assert source.content == "raw text"
    assert source.metadata == {"kind": "note"}


def test_malformed_response_raises_rather_than_silently_dropping(store):
    mem, _ = make_memory(store, ["I'm afraid I can't do that."])
    with pytest.raises(MalformedResponseError):
        mem.remember("a fact that must not vanish")


# -- multi-tenancy -----------------------------------------------------


def test_projects_are_isolated(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "acme uses uv")),
            merge(edit("create", "tooling", "globex uses poetry")),
        ],
    )
    mem.remember("a", project_id="acme")
    mem.remember("b", project_id="globex")

    assert mem.page("tooling", project_id="acme").body == "acme uses uv"
    assert mem.page("tooling", project_id="globex").body == "globex uses poetry"
    assert mem.pages(project_id="acme") != mem.pages(project_id="globex")
    assert store.search("acme", "poetry") == []


# -- concurrency -------------------------------------------------------


def test_concurrent_edit_is_rejected(store):
    store.apply("default", [(Page(slug="p", title="P", body="v1"), None)], [])
    store.apply("default", [(Page(slug="p", title="P", body="v2"), 1)], [])

    stale = Page(slug="p", title="P", body="from a stale read")
    with pytest.raises(ConcurrentEditError):
        store.apply("default", [(stale, 1)], [])
    assert store.get_page("default", "p").body == "v2"


def test_a_rejected_batch_rolls_back_entirely(store):
    store.apply("default", [(Page(slug="a", title="A", body="v1"), None)], [])
    good = Page(slug="b", title="B", body="new")
    stale = Page(slug="a", title="A", body="stale")

    with pytest.raises(ConcurrentEditError):
        store.apply("default", [(good, None), (stale, 99)], [])

    assert store.get_page("default", "b") is None
    assert store.get_page("default", "a").body == "v1"


def test_creating_a_page_that_already_exists_is_rejected(store):
    store.apply("default", [(Page(slug="p", title="P", body="v1"), None)], [])
    with pytest.raises(ConcurrentEditError):
        store.apply("default", [(Page(slug="p", title="P", body="v2"), None)], [])


# -- retrieval ---------------------------------------------------------


def test_search_finds_pages_by_body_text(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "The team uses uv for packaging.")),
            select(),
            merge(edit("create", "travel", "Flights to Chennai in March.")),
        ],
    )
    mem.remember("a")
    mem.remember("b")

    assert [p.slug for p in mem.search("packaging")] == ["tooling"]
    assert [p.slug for p in mem.search("Chennai")] == ["travel"]


def test_search_reflects_the_latest_body_not_the_old_one(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "uses poetry")),
            select(open_slugs=["tooling"]),
            merge(edit("update", "tooling", "uses uv")),
        ],
    )
    mem.remember("a")
    mem.remember("b")

    assert mem.search("uv")
    assert mem.search("poetry") == []


def test_ask_cites_the_pages_it_read(store):
    mem, llm = make_memory(
        store,
        [
            merge(edit("create", "tooling", "The team uses uv.")),
            "They use uv [[tooling]].",
        ],
    )
    mem.remember("a")
    answer = mem.ask("what do they use?")

    assert answer.citations == ["tooling"]
    assert "uv" in answer.text


def test_ask_on_an_empty_base_does_not_call_the_model(store):
    mem, llm = make_memory(store, [])
    answer = mem.ask("anything?")
    assert answer.pages == []
    assert llm.calls == []


# -- lint --------------------------------------------------------------


def test_lint_reports_broken_links_without_the_model(store):
    store.apply(
        "default",
        [(Page(slug="a", title="A", body="see [[missing]] and [[a]]"), None)],
        [],
    )
    mem, llm = make_memory(store, [{"findings": []}])
    findings = mem.lint()

    assert [f.kind for f in findings] == ["broken_link"]
    assert "missing" in findings[0].detail


def test_lint_drops_findings_about_unknown_pages(store):
    store.apply("default", [(Page(slug="a", title="A", body="x"), None)], [])
    mem, _ = make_memory(
        store,
        [
            {
                "findings": [
                    {"kind": "contradiction", "slugs": ["ghost"], "detail": "d"},
                    {"kind": "nonsense", "slugs": ["a"], "detail": "d"},
                ]
            }
        ],
    )
    assert mem.lint() == []


def test_lint_on_an_empty_base_does_nothing(store):
    mem, llm = make_memory(store, [])
    assert mem.lint() == []
    assert llm.calls == []


# -- schema and log ----------------------------------------------------


def test_schema_doc_is_per_project_and_reaches_the_compactor(store):
    mem, llm = make_memory(store, [merge(edit("create", "a", "b"))])
    mem.set_schema_doc("Only record food preferences.")
    mem.remember("a fact")

    merge_prompt = llm.calls[-1][-1]["content"]
    assert "Only record food preferences." in merge_prompt
    assert mem.schema_doc == "Only record food preferences."


def test_log_records_each_operation(store):
    mem, _ = make_memory(
        store,
        [
            merge(edit("create", "tooling", "v1")),
            select(open_slugs=["tooling"]),
            merge(edit("update", "tooling", "v2")),
        ],
    )
    mem.remember("a")
    mem.remember("b")

    ops = [e.op for e in mem.log()]
    assert "ingest.create" in ops
    assert "ingest.update" in ops


def test_log_is_newest_first(store):
    now = utcnow()
    store.apply(
        "default",
        [],
        [
            LogEntry(ts=now.replace(microsecond=1), op="first", detail=""),
            LogEntry(ts=now.replace(microsecond=2), op="second", detail=""),
        ],
    )
    assert [e.op for e in store.log("default")] == ["second", "first"]


# -- persistence -------------------------------------------------------


def test_pages_survive_reopening_the_database(tmp_path):
    db = tmp_path / "kb.db"
    mem, _ = make_memory(
        SQLiteKnowledgeStore(db), [merge(edit("create", "tooling", "uses uv"))]
    )
    mem.remember("a")

    reopened = KnowledgeMemory(store=SQLiteKnowledgeStore(db), llm=ScriptedLLM([]))
    assert reopened.page("tooling").body == "uses uv"
    assert [p.slug for p in reopened.search("uv")] == ["tooling"]


# -- helpers -----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure!\n```\n{"a": 1}\n```\nHope that helps', {"a": 1}),
        ('Here you go: {"a": 1}', {"a": 1}),
    ],
)
def test_parse_json_object_is_tolerant(raw, expected):
    assert parse_json_object(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "no json here", "[1, 2, 3]"])
def test_parse_json_object_rejects_junk(raw):
    with pytest.raises(MalformedResponseError):
        parse_json_object(raw)


def test_slugify():
    assert slugify("Topic: Tooling & Build!") == "topic-tooling-build"
    assert slugify("!!!") == "untitled"
    assert len(slugify("x" * 200)) == 80


def test_fts_query_drops_stopwords_and_punctuation():
    assert _fts_query("the user's name is Shrijayan") == "user OR name OR shrijayan"
    assert _fts_query("the a an of") == ""


def test_page_renders_as_markdown_with_frontmatter():
    page = Page(slug="a", title="A", body="body", frontmatter={"summary": "s"})
    rendered = page.to_markdown()
    assert rendered.startswith("---\nsummary: s\n---")
    assert "# A" in rendered
