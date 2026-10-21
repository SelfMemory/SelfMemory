"""The database-free engine: sandbox argv, agent I/O, OKF files, git, graph, search."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from selfmemory.features.runs.adapters.opencode import (
    RunPlan,
    agent_argv,
    install_agent_config,
    parse_event,
    render_prompt,
)
from selfmemory.features.uploads.convert import convert_file
from selfmemory.features.wiki.adapters import git_repo as git
from selfmemory.features.wiki.adapters.graph import (
    ScopeRoot,
    build_graph,
    build_timeline,
    outbound_links,
)
from selfmemory.features.wiki.adapters.okf import (
    parse_frontmatter,
    parse_promotions,
    scaffold_scope,
    set_promotion_status,
)
from selfmemory.features.wiki.adapters.search import search_pages
from selfmemory.platform.sandbox.sandbox import RunSpec, build_argv

if TYPE_CHECKING:
    from pathlib import Path

# ------------------------------------------------------------------ sandbox


def _spec(tmp_path: Path, **kw) -> RunSpec:
    parent = tmp_path / "wiki" / "projects" / "p"
    child = parent / "c"
    child.mkdir(parents=True)
    defaults = {
        "read_dirs": [parent, child],
        "write_dir": None,
        "agent_home": tmp_path / ".agent",
        "agent_bin": "/opt/agent/bin/opencode",
        "cwd": tmp_path,
        "argv": ["opencode", "run", "x"],
        "mask_dirs": [child],
    }
    defaults.update(kw)
    return RunSpec(**defaults)


def test_readable_child_is_mounted_not_masked(tmp_path):
    spec = _spec(tmp_path)
    args = build_argv("bwrap", spec)
    parent = str(tmp_path / "wiki" / "projects" / "p")
    child = parent + "/c"
    # parent first, then the child's own read-only bind on top; no tmpfs mask,
    # which docker would reject as a duplicate mount point
    assert args.index(parent) < args.index(child)
    assert args[args.index(child) - 1] == "--ro-bind"
    assert args.count(child) == 2
    assert args[-3:] == ["opencode", "run", "x"]
    cargs = build_argv("container", spec)
    assert f"type=tmpfs,destination={child}" not in cargs
    assert f"{child}:{child}:ro" in cargs


def test_bwrap_masks_unreadable_child_without_remount(tmp_path):
    spec = _spec(tmp_path)
    spec.read_dirs = spec.read_dirs[:1]
    args = build_argv("bwrap", spec)
    child = str(tmp_path / "wiki" / "projects" / "p" / "c")
    assert args.count(child) == 1  # only the tmpfs mask
    assert args[args.index(child) - 1] == "--tmpfs"


def test_container_mounts_write_scope_rw_and_drops_caps(tmp_path):
    write = tmp_path / "wiki" / "projects" / "p"
    spec = _spec(tmp_path, write_dir=write, agent_in_image=True, image="img:1")
    args = build_argv("container", spec)
    assert "--cap-drop" in args and "ALL" in args
    assert f"{write}:{write}:rw" in args
    assert f"{write}:{write}:ro" not in args  # write scope is not also mounted ro
    assert args[args.index("img:1") + 1 :] == ["opencode", "run", "x"]
    assert not any("/opt/agent/bin/opencode:" in a for a in args)


# -------------------------------------------------------------------- agent

# Captured from a real `opencode run --format json` (v2) session.
REAL_LINES = [
    '{"type":"step_start","sessionID":"ses_1","part":{"type":"step-start"}}',
    '{"type":"tool_use","sessionID":"ses_1","part":{"type":"tool","tool":"read",'
    '"state":{"status":"completed","title":"read"}}}',
    '{"type":"step_finish","sessionID":"ses_1","part":{"type":"step-finish","cost":0,'
    '"tokens":{"input":6908,"output":18,"reasoning":14,"cache":{"read":4608,"write":0}}}}',
    '{"type":"text","sessionID":"ses_1","part":{"type":"text","text":"The sky is green."}}',
]


def test_parse_real_opencode_stream():
    events = [e for line in REAL_LINES for e in parse_event(line)]
    kinds = [e["kind"] for e in events if e["kind"] != "session"]
    assert kinds == ["tool", "usage", "text"]
    assert events[-1]["text"] == "The sky is green."
    usage = next(e for e in events if e["kind"] == "usage")
    assert usage["tokens"]["input"] == 6908
    assert {e["session_id"] for e in events if e["kind"] == "session"} == {"ses_1"}


def test_parse_error_and_garbage():
    err = json.dumps({"type": "error", "error": {"type": "x", "message": "no route"}})
    assert parse_event(err)[-1] == {"kind": "error", "message": "no route"}
    assert parse_event("not json") == []
    assert parse_event("[1,2]") == []


def test_prompt_names_write_root_and_readable_dirs(tmp_path):
    org = tmp_path / "org1"
    plan = RunPlan(
        command="ingest",
        message="raw/projects/p/deck.pptx.md",
        org_root=org,
        read_dirs=[org / "wiki" / "org"],
        write_dir=org / "wiki" / "projects" / "p",
        scope_labels={"wiki/projects/p": "Payments"},
    )
    prompt = render_prompt(plan)
    assert "SCOPE_ROOT for this run is wiki/projects/p" in prompt
    assert "wiki/projects/p = Payments" in prompt
    assert "raw/projects/p/deck.pptx.md" in prompt
    assert "$ARGUMENTS" not in prompt


def test_agent_argv_selects_agent_and_session(settings, tmp_path):
    plan = RunPlan("query", "q?", tmp_path, [tmp_path], None, session_id="ses_9")
    argv = agent_argv(settings, plan, "opencode")
    assert argv[:2] == ["opencode", "run"]
    assert argv[argv.index("--agent") + 1] == "selfmemory-query"
    assert argv[argv.index("--session") + 1] == "ses_9"
    assert "--standalone" in argv
    with pytest.raises(ValueError):
        render_prompt(RunPlan("rm", "x", tmp_path, [], None))


def test_install_agent_config_keeps_operator_opencode_json(settings):
    cfg = settings.agent_home / ".config" / "opencode"
    cfg.mkdir(parents=True)
    (cfg / "opencode.json").write_text('{"model": "mine"}')
    install_agent_config(settings)
    assert (cfg / "agent" / "selfmemory-ingest.md").exists()
    assert "SelfMemory" in (cfg / "AGENTS.md").read_text()
    assert json.loads((cfg / "opencode.json").read_text()) == {"model": "mine"}


# --------------------------------------------------------- okf, git, graph


def _page(scope: Path, rel: str, body: str) -> None:
    p = scope / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_scaffold_is_idempotent_and_commits(tmp_path):
    scope = tmp_path / "wiki" / "projects" / "p"
    sha = scaffold_scope(scope, "project:p", "P")
    assert sha and (scope / "promotions.md").exists()
    meta, _ = parse_frontmatter((scope / "index.md").read_text())
    assert meta == {"okf_version": "0.2"}
    assert scaffold_scope(scope, "project:p", "P") is None
    assert git.commit_scope(scope, "noop") is None


def test_parent_repo_excludes_nested_sub_project(tmp_path):
    parent = tmp_path / "wiki" / "projects" / "p"
    scaffold_scope(parent, "project:p", "P", nested=("c",))
    child = parent / "c"
    scaffold_scope(child, "project:c", "C")
    _page(child, "secret/plan.md", "---\ntype: Plan\n---\nchild only")
    git.commit_scope(child, "child")
    assert git.commit_scope(parent, "parent", nested=("c",)) is None
    assert not any(
        f.startswith("c/") or f == "c" for f in git.tree_files(parent, "HEAD")
    )


def test_links_resolve_okf_styles():
    links = outbound_links(
        "[a](/tables/orders.md) [b](../people/ada.md#x) [[tables/customers]] "
        "[[sibling|alias]] [ext](https://x.com/a.md)",
        "wiki/org/policies/sec.md",
        "wiki/org",
    )
    assert links == [
        "wiki/org/tables/customers.md",
        "wiki/org/policies/sibling.md",
        "wiki/org/tables/orders.md",
        "wiki/org/people/ada.md",
    ]


def test_graph_and_timeline(tmp_path):
    org = tmp_path
    scope = org / "wiki" / "org"
    scaffold_scope(scope, "org", "Org")
    _page(
        scope,
        "tables/orders.md",
        "---\ntype: Table\n---\nJoins [c](/tables/customers.md)",
    )
    _page(scope, "tables/customers.md", "---\ntype: Table\n---\nCustomers")
    _page(scope, "tables/x.md", "[missing](/nope.md)")
    git.commit_scope(scope, "add tables")
    root = ScopeRoot("org", "wiki/org", scope)
    g = build_graph(org, [root])
    ids = {n["id"] for n in g["nodes"]}
    assert "wiki/org/tables/orders.md" in ids
    assert {
        "from": "wiki/org/tables/orders.md",
        "to": "wiki/org/tables/customers.md",
    } in g["edges"]
    assert g["broken"] == 1
    frames = build_timeline([root])
    assert len(frames) == 2
    assert "wiki/org/tables/orders.md" not in frames[0]["nodes"]
    assert ["wiki/org/tables/orders.md", "wiki/org/tables/customers.md"] in frames[1][
        "edges"
    ]


def test_graph_excludes_unreadable_child(tmp_path):
    parent = tmp_path / "wiki" / "projects" / "p"
    _page(parent, "a.md", "x")
    _page(parent, "c/hidden.md", "x")
    root = ScopeRoot(
        "project:p", "wiki/projects/p", parent, exclude=("wiki/projects/p/c",)
    )
    ids = {n["id"] for n in build_graph(tmp_path, [root])["nodes"]}
    assert ids == {"wiki/projects/p/a.md"}


def test_search_ranks_title_hits(tmp_path):
    scope = tmp_path / "wiki" / "org"
    _page(
        scope,
        "policies/security.md",
        "---\ntype: Policy\ntitle: Security policy\n---\nRotate keys.",
    )
    _page(scope, "misc/notes.md", "---\ntype: Note\n---\nsecurity mentioned once")
    _page(scope, "index.md", "security security security")
    hits = search_pages(
        tmp_path, [ScopeRoot("org", "wiki/org", scope)], "security policy"
    )
    assert [h["path"] for h in hits] == [
        "wiki/org/policies/security.md",
        "wiki/org/misc/notes.md",
    ]
    assert hits[0]["title"] == "Security policy"


def test_promotions_parse_and_status_rewrite():
    text = (
        "# Promotions\n\n"
        "## [2026-10-01] proposed | All laptops use disk encryption\n"
        "source: raw/projects/p/it.md\n"
        "rationale: company policy\n"
    )
    [p] = parse_promotions(text)
    assert (p.fact, p.source, p.status) == (
        "All laptops use disk encryption",
        "raw/projects/p/it.md",
        "proposed",
    )
    updated = set_promotion_status(text, p.id, "approved")
    assert parse_promotions(updated)[0].status == "approved"
    assert parse_promotions(updated)[0].id == p.id
    with pytest.raises(KeyError):
        set_promotion_status(text, "nope", "approved")


# ------------------------------------------------------------------ convert


def test_convert_text_image_and_binary(tmp_path):
    t = tmp_path / "a"
    t.write_text("plain notes")
    assert convert_file("notes.txt", t).name == "notes.txt"
    img = tmp_path / "b"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    c = convert_file("diagram.png", img)
    assert c.name == "diagram.png.md" and c.asset == "diagram.png"
    assert b"assets/diagram.png" in c.content
    blob = tmp_path / "c"
    blob.write_bytes(b"\x00\x01\x02" * 100)
    assert convert_file("data.bin", blob).asset == "data.bin"


def test_convert_html_with_markitdown(tmp_path):
    pytest.importorskip("markitdown")
    h = tmp_path / "h"
    h.write_text("<html><body><h1>Title</h1><p>Body text</p></body></html>")
    c = convert_file("page.html", h)
    assert c.name == "page.html.md" and c.converted_by == "markitdown"
    assert b"Body text" in c.content


def test_missing_sub_project_dirs_are_created_and_masked(tmp_path):
    missing_child = tmp_path / "wiki" / "projects" / "p" / "later"
    missing_git = tmp_path / "wiki" / "projects" / "p" / ".git"
    spec = _spec(tmp_path, mask_dirs=[missing_child, missing_git])
    args = build_argv("bwrap", spec)
    # an unscaffolded child is still hidden, so an ingest cannot pre-seed it
    assert missing_child.is_dir()
    assert args[args.index(str(missing_child)) - 1] == "--tmpfs"
    # but an empty .git is never invented (it would read as a repository)
    assert not missing_git.exists()
    assert str(missing_git) not in args


def test_container_runs_are_named_for_kill(tmp_path):
    spec = _spec(tmp_path, name="selfmemory-run-abc")
    args = build_argv("container", spec)
    assert args[args.index("--name") + 1] == "selfmemory-run-abc"
