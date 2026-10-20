#!/usr/bin/env python
"""Run the compactor against a real model to inspect merge quality.

    uv run python scripts/knowledge_demo.py
    uv run python scripts/knowledge_demo.py --provider openai --model gpt-4.1

Feeds a sequence of overlapping, partly contradictory facts one at a time and
prints what each ingest did. The thing to watch is whether later facts *update*
earlier pages instead of piling up near-duplicates, and whether the
contradiction on line 4 lands under "## Superseded" rather than silently
replacing the earlier claim.
"""

from __future__ import annotations

import argparse

from selfmemory.knowledge import KnowledgeMemory

FACTS = [
    "Shrijayan works on selfmemory, a Python memory backend for AI agents.",
    "selfmemory uses uv as its package manager, never pip.",
    "Shrijayan prefers ruff for both linting and formatting, line length 88.",
    "Correction: selfmemory moved off Qdrant; it no longer uses a vector store.",
    "The selfmemory server validates sessions against Ory Kratos and Hydra.",
    "Shrijayan is based in Chennai and prefers async work over meetings.",
    "selfmemory is multi-tenant: organizations contain projects contain users.",
]

QUESTIONS = [
    "What package manager does selfmemory use?",
    "Does selfmemory use a vector database?",
    "How does auth work?",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--model", default=None)
    parser.add_argument("--db", default=":memory:")
    args = parser.parse_args()

    config = {"model": args.model} if args.model else None
    mem = KnowledgeMemory(
        db_path=args.db, llm_provider=args.provider, llm_config=config
    )

    print("=" * 72)
    print("INGEST")
    print("=" * 72)
    for fact in FACTS:
        result = mem.remember(fact)
        print(f"\n> {fact}")
        for edit in result.edits:
            print(f"    {edit.op:6} {edit.slug:28} {edit.reason}")
        if not result.edits:
            print("    (no change)")

    print("\n" + "=" * 72)
    print(f"PAGES ({len(mem.pages())})")
    print("=" * 72)
    for page in mem.pages():
        print(f"\n{page.to_markdown()}")

    print("=" * 72)
    print("ASK")
    print("=" * 72)
    for question in QUESTIONS:
        answer = mem.ask(question)
        print(f"\n> {question}\n{answer.text}\n  cited: {answer.citations}")

    print("\n" + "=" * 72)
    print("LINT")
    print("=" * 72)
    findings = mem.lint()
    for finding in findings:
        print(
            f"\n{finding.kind}: {finding.slugs}\n  {finding.detail}\n  fix: {finding.fix}"
        )
    if not findings:
        print("\nclean")


if __name__ == "__main__":
    main()
