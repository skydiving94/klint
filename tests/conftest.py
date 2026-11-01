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
from tests.support.stub_system_one_server import StubSystemOneServer


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
def system_one_server(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[StubSystemOneServer]:
    """Start a local stand-in for a System One endpoint.

    The stand-in is the one address the test may connect to; any other
    connection still fails. Proxy settings are cleared so that the judge
    reaches it directly.
    """
    server = StubSystemOneServer()
    blocked_connect = socket.socket.connect

    def connect_to_the_stub_only(
        connecting_socket: socket.socket, address: tuple[str, int]
    ) -> None:
        if address == server.address:
            super(socket.socket, connecting_socket).connect(address)
            return
        blocked_connect(connecting_socket, address)

    monkeypatch.setattr(socket.socket, "connect", connect_to_the_stub_only)
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    server.start()
    yield server
    server.stop()


@pytest.fixture
def shell_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Give the test a private environment with no klint setting set.

    No KLINT_* variable is set, nor any KEV_* one that the KLINT_* ones
    replace. The settings a test sees then do not depend on the shell it runs from.
    The working directory moves to an empty folder so that no stray
    klint.json is discovered there.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KLINT_", "KEV_"))}
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
