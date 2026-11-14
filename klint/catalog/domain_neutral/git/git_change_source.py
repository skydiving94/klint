"""Reads a change from a git repository: one commit, or the change since a commit."""

import asyncio
import os
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git.git_change import GitChange
from klint.catalog.domain_neutral.git.git_diff_parser import parse_git_diff
from klint.core.interfaces import (
    BaseAuditSource,
    BaseAuditSourceFactory,
    BaseScanProgressListener,
)
from klint.core.models.audits import AuditInput, DiskPathInput

# What every diff is asked for, whatever the user's git settings: paths as
# they are, renames found and copies not, plain text, no lines of context.
_DIFF_ARGUMENTS = (
    "-c",
    "core.quotePath=false",
    "-c",
    "diff.renames=true",
    "diff",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--unified=0",
    "--find-renames",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)


@dataclass(frozen=True)
class _GitOutput:
    """What one git command gave back: its exit status and what it printed."""

    return_code: int
    stdout: str
    stderr: str


class GitChangeSource(BaseAuditSource[GitChange]):
    """Reads the change of the repository a directory is in.

    With a commit, the change is that commit, against its first parent. With
    a base, it is everything since that commit, committed or not, up to the
    working tree. With neither, it is the uncommitted change against HEAD.
    The last two take the working tree staged or not, untracked files
    included and ignored files left out. The repository itself is left as
    it is.
    """

    def __init__(
        self, directory: Path, commit: str | None = None, base: str | None = None
    ) -> None:
        if commit is not None and base is not None:
            raise ValueError(
                "A git change is read from a commit or since a base, not both"
            )
        self._directory = directory
        self._commit = commit
        self._base = base
        self._scanned_file_count = 0

    async def read_input(self) -> GitChange:
        """Return the change.

        Raises ValueError when git cannot be run, the directory is not in a
        git repository, or the commit or base is not known.
        """
        repository_path = await self._find_repository_path()
        if self._commit is None:
            diff_command, diff_text = await _diff_working_tree(
                repository_path, self._base
            )
        else:
            diff_command, diff_text = await _diff_commit(repository_path, self._commit)
        files = tuple(parse_git_diff(diff_text))
        self._scanned_file_count = len(files)
        return GitChange(
            repository_path=repository_path, diff_command=diff_command, files=files
        )

    def count_scanned_files(self) -> int:
        """Return the number of changed files read."""
        return self._scanned_file_count

    async def _find_repository_path(self) -> Path:
        output = await _run_git(["rev-parse", "--show-toplevel"], self._directory)
        if output.return_code != 0:
            raise ValueError(
                f"'{self._directory}' is not in a git repository: "
                f"{output.stderr.strip()}"
            )
        return Path(output.stdout.strip())


class GitChangeSourceFactory(BaseAuditSourceFactory[GitChange]):
    """Makes the source of the change in the repository a directory on disk is in.

    commit names the commit to read, as git names one, such as "HEAD" or a
    hash. base names the commit the change starts from, up to the working
    tree. With neither, the uncommitted change is read.
    """

    def __init__(self, commit: str | None = None, base: str | None = None) -> None:
        self._commit = commit
        self._base = base

    def create_source(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> GitChangeSource:
        """Return the source of the change; no directory is scanned.

        Raises ValueError when ``audit_input`` is not a directory on disk.
        """
        del scan_progress_listener
        if not isinstance(audit_input, DiskPathInput):
            raise ValueError("A git change is read from a directory on disk")
        return GitChangeSource(audit_input.path, self._commit, self._base)


async def _diff_commit(repository_path: Path, commit: str) -> tuple[str, str]:
    """Return the command diffing ``commit`` with its first parent, and its output."""
    commit_hash = await _resolve_commit(repository_path, f"{commit}^{{commit}}")
    if commit_hash is None:
        raise ValueError(f"The repository '{repository_path}' has no commit '{commit}'")
    parent_hash = await _resolve_commit(repository_path, f"{commit_hash}^1^{{commit}}")
    base = parent_hash or await _find_empty_tree(repository_path)
    diff_text = await _run_git_or_raise(
        [*_DIFF_ARGUMENTS, base, commit_hash], repository_path
    )
    base_name = f"{commit}^" if parent_hash else base
    return f"git diff -U0 {base_name} {commit}", diff_text


async def _diff_working_tree(
    repository_path: Path, base_commit: str | None
) -> tuple[str, str]:
    """Return the command diffing the working tree with ``base_commit``, and its output.

    The base is HEAD when ``base_commit`` is None. The untracked files are
    diffed through a copy of the index that marks them as to be added, so
    that the repository's own index is left alone.
    """
    if base_commit is None:
        head_hash = await _resolve_commit(repository_path, "HEAD^{commit}")
        base = head_hash or await _find_empty_tree(repository_path)
        base_name = "HEAD" if head_hash else base
    else:
        base_hash = await _resolve_commit(repository_path, f"{base_commit}^{{commit}}")
        if base_hash is None:
            raise ValueError(
                f"The repository '{repository_path}' has no commit '{base_commit}'"
            )
        base = base_name = base_hash
    diff_command = f"git diff -U0 {base_name}, untracked files included"
    untracked_paths = await _list_untracked_paths(repository_path)
    if not untracked_paths:
        diff_text = await _run_git_or_raise([*_DIFF_ARGUMENTS, base], repository_path)
        return diff_command, diff_text
    with tempfile.TemporaryDirectory() as temporary_directory:
        index_path = Path(temporary_directory) / "index"
        await _copy_index(repository_path, index_path)
        await _run_git_or_raise(
            [
                "--literal-pathspecs",
                "add",
                "--intent-to-add",
                "--pathspec-from-file=-",
                "--pathspec-file-nul",
            ],
            repository_path,
            stdin_text="\0".join(untracked_paths),
            index_path=index_path,
        )
        diff_text = await _run_git_or_raise(
            [*_DIFF_ARGUMENTS, base], repository_path, index_path=index_path
        )
    return diff_command, diff_text


async def _resolve_commit(repository_path: Path, revision: str) -> str | None:
    """Return the hash ``revision`` names; None when it names no commit."""
    output = await _run_git(
        ["rev-parse", "--verify", "--quiet", "--end-of-options", revision],
        repository_path,
    )
    return output.stdout.strip() if output.return_code == 0 else None


async def _find_empty_tree(repository_path: Path) -> str:
    """Return the hash of the empty tree, what a first commit is diffed against."""
    return (
        await _run_git_or_raise(
            ["hash-object", "-t", "tree", "--stdin"], repository_path, stdin_text=""
        )
    ).strip()


async def _list_untracked_paths(repository_path: Path) -> list[str]:
    """Return the path of each untracked file that is not ignored."""
    output = await _run_git_or_raise(
        ["ls-files", "--others", "--exclude-standard", "-z"], repository_path
    )
    return [path for path in output.split("\0") if path]


async def _copy_index(repository_path: Path, index_path: Path) -> None:
    """Copy the repository's index, if it has one, to ``index_path``."""
    git_index_path = Path(
        (
            await _run_git_or_raise(
                ["rev-parse", "--path-format=absolute", "--git-path", "index"],
                repository_path,
            )
        ).strip()
    )
    if git_index_path.exists():
        await asyncio.to_thread(shutil.copyfile, git_index_path, index_path)


async def _run_git_or_raise(
    arguments: Sequence[str],
    directory: Path,
    *,
    stdin_text: str | None = None,
    index_path: Path | None = None,
) -> str:
    """Return what the git command printed. Raises ValueError when it fails."""
    output = await _run_git(
        arguments, directory, stdin_text=stdin_text, index_path=index_path
    )
    if output.return_code != 0:
        raise ValueError(
            f"git {' '.join(arguments)} failed in '{directory}': "
            f"{output.stderr.strip()}"
        )
    return output.stdout


async def _run_git(
    arguments: Sequence[str],
    directory: Path,
    *,
    stdin_text: str | None = None,
    index_path: Path | None = None,
) -> _GitOutput:
    """Run git with ``arguments`` in ``directory``, on ``index_path`` when given."""
    environment = None
    if index_path is not None:
        environment = {**os.environ, "GIT_INDEX_FILE": str(index_path)}
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *arguments,
            cwd=directory,
            env=environment,
            stdin=asyncio.subprocess.DEVNULL
            if stdin_text is None
            else asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise ValueError("git cannot be run: it is not on the PATH") from error
    except NotADirectoryError as error:
        raise ValueError(f"'{directory}' is not a directory") from error
    stdout, stderr = await process.communicate(
        None if stdin_text is None else stdin_text.encode("utf-8")
    )
    return _GitOutput(
        return_code=process.returncode or 0,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
