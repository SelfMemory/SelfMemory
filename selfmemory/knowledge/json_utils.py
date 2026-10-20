"""Tolerant JSON extraction from LLM responses."""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class MalformedResponseError(ValueError):
    """The model returned something we could not read as JSON."""


def parse_json_object(text: str) -> dict:
    """Pull the first JSON object out of a model response.

    Models wrap JSON in prose or code fences often enough that this needs to be
    forgiving, but it must never silently return an empty result -- a swallowed
    parse failure would look like "the source changed nothing".
    """
    if not text or not text.strip():
        raise MalformedResponseError("empty response")

    candidates = [m.strip() for m in _FENCE_RE.findall(text)]
    candidates.append(text.strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    preview = text[:200].replace("\n", " ")
    raise MalformedResponseError(f"no JSON object in response: {preview!r}")
