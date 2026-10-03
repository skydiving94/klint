"""Shared pytest fixtures: network block, working directory and snapshots."""

import os
import socket
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.helpers import REPO_ROOT, SNAPSHOT_DIR, FakeJudge, SnapshotAsserter


@pytest.fixture
def fake_judge() -> type[FakeJudge]:
    """Return the FakeJudge class, so a test can build one with its own answers."""
    return FakeJudge


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a network connection."""
    blocked = Mock(side_effect=RuntimeError("network access is not allowed in tests"))
    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.fixture
def in_repo_root(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run from the repo root so unit ids and paths in output stay relative."""
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT


@pytest.fixture
def assert_snapshot() -> SnapshotAsserter:
    """Compare text with ``tests/snapshots/<name>``.

    Set ``UPDATE_SNAPSHOTS=1`` to (re)write the stored file, then review it.
    """

    def _assert(name: str, actual: str) -> None:
        path = SNAPSHOT_DIR / name
        if os.environ.get("UPDATE_SNAPSHOTS") == "1":
            path.write_text(actual, encoding="utf-8")
            return
        assert path.is_file(), (
            f"missing snapshot {path}; run with UPDATE_SNAPSHOTS=1 to create it"
        )
        assert actual == path.read_text(encoding="utf-8")

    return _assert
