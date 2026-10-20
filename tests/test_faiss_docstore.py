"""FAISS docstore persistence.

Skipped unless the optional faiss package is installed.
"""

from __future__ import annotations

import pickle

import pytest

pytest.importorskip("faiss")

from selfmemory.vector_stores.faiss import FAISS  # noqa: E402

DIMS = 4


def _store(path) -> FAISS:
    return FAISS(collection_name="mem", path=str(path), embedding_model_dims=DIMS)


def test_docstore_round_trips_through_json(tmp_path):
    store = _store(tmp_path)
    store.insert(
        vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
        payloads=[{"data": "first", "user_id": "u1"}, {"data": "second"}],
        ids=["id-a", "id-b"],
    )

    assert (tmp_path / "mem.json").exists()
    assert not (tmp_path / "mem.pkl").exists()

    reloaded = _store(tmp_path)
    assert reloaded.get("id-a").payload["data"] == "first"
    assert reloaded.get("id-b").payload["data"] == "second"
    # FAISS row ids must come back as ints, not the strings JSON stores.
    assert all(isinstance(k, int) for k in reloaded.index_to_id)


class _Exploit:
    """Unpickling this writes a marker file -- proof that code ran."""

    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return (open, (self.marker, "w"))


def test_a_legacy_pickle_is_refused_and_never_executed(tmp_path):
    store = _store(tmp_path)
    store.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{}], ids=["x"])
    (tmp_path / "mem.json").unlink()

    marker = tmp_path / "pwned"
    (tmp_path / "mem.pkl").write_bytes(pickle.dumps(_Exploit(str(marker))))

    with pytest.raises(RuntimeError, match="legacy pickle docstore") as exc:
        _store(tmp_path)

    assert not marker.exists(), "the pickle was executed"
    assert "convert it once" in str(exc.value)


def test_delete_removes_json_and_any_legacy_pickle(tmp_path):
    store = _store(tmp_path)
    store.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{}], ids=["x"])
    (tmp_path / "mem.pkl").write_bytes(b"stale")

    store.delete_col()

    assert not (tmp_path / "mem.json").exists()
    assert not (tmp_path / "mem.pkl").exists()
    assert not (tmp_path / "mem.faiss").exists()
