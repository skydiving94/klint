"""Shared pytest fixtures: network block, working directory and snapshots."""

import os
import socket
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.support.builders import MakeUnreadable
from tests.support.fakes import FakeJudge
from tests.support.paths import REPO_ROOT, SNAPSHOT_DIR, SnapshotAsserter


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
def shell_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Give the test a private environment with no KEV_* variables set.

    Settings loading writes into ``os.environ``, so each test gets its own
    copy. The working directory moves to an empty folder so that no stray
    klint.json is discovered there.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("KEV_")}
    monkeypatch.setattr(os, "environ", env)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return env


@pytest.fixture
def make_unreadable() -> Iterator[MakeUnreadable]:
    """Return a function that takes every permission away from a path.

    The permissions are given back after the test, so that its folder can be
    removed. The test is skipped where taking them away does not stop
    reading, as for root.
    """
    path_to_mode: dict[Path, int] = {}

    def _make_unreadable(path: Path) -> Path:
        path_to_mode[path] = path.stat().st_mode
        path.chmod(0)
        if os.access(path, os.R_OK):
            pytest.skip("permissions do not stop this user from reading")
        return path

    yield _make_unreadable
    for path, mode in path_to_mode.items():
        path.chmod(mode)


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
