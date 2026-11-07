"""Temporary git repositories for tests, built with the git command."""

import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

# The settings every test repository runs git with, whatever the machine's:
# no user or system configuration, and a fixed committer.
_GIT_ENVIRONMENT = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "klint tests",
    "GIT_AUTHOR_EMAIL": "tests@klint.invalid",
    "GIT_COMMITTER_NAME": "klint tests",
    "GIT_COMMITTER_EMAIL": "tests@klint.invalid",
}


def isolate_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run git, in this test and in klint, with no user or system configuration."""
    empty_config = tmp_path / "gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    for name, value in _GIT_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


def run_git(repository: Path, *arguments: str) -> str:
    """Run git in ``repository`` and return what it printed."""
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def write_files(repository: Path, path_to_content: Mapping[str, str | bytes]) -> None:
    """Write each file under ``repository``, creating its folders."""
    for path, content in path_to_content.items():
        file_path = repository / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content, encoding="utf-8")


def commit_everything(repository: Path, message: str) -> str:
    """Commit every change in ``repository``, untracked files too; return the hash."""
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "--quiet", "--message", message)
    return run_git(repository, "rev-parse", "HEAD").strip()


def create_repository(
    repository: Path, path_to_content: Mapping[str, str | bytes]
) -> Path:
    """Create a repository holding the files given, in one commit; return its path."""
    repository.mkdir(parents=True, exist_ok=True)
    run_git(repository, "init", "--quiet", "--initial-branch", "main")
    write_files(repository, path_to_content)
    commit_everything(repository, "Starting the project")
    return repository
