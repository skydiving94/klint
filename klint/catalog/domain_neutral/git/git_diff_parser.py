"""Reads a unified diff in git's format into changed files and their hunks.

Any such diff is read, with or without lines of context, with the "a/" and
"b/" prefixes, other one-folder prefixes, or none. Each hunk is given as
``git diff --unified=0`` would give it: a hunk with lines of context
becomes one hunk for each run of changed lines in it.
"""

from dataclasses import dataclass

from klint.catalog.domain_neutral.git.git_change import (
    ChangeKind,
    GitFileChange,
    GitHunk,
    HunkHeader,
    parse_hunk_header,
)
from klint.catalog.domain_neutral.git.git_diff_paths import (
    find_path_of_unrenamed_file,
    unquote_path,
)

_FILE_HEADER_PREFIX = "diff --git "
_COMBINED_HEADER_PREFIXES = ("diff --cc ", "diff --combined ")
_HUNK_HEADER_PREFIX = "@@ "
_INDEX_PREFIX = "index "
_NO_NEWLINE_MARKER_PREFIX = "\\"
_HEADER_PREFIX_TO_KIND = {
    "new file mode ": ChangeKind.ADDED,
    "deleted file mode ": ChangeKind.DELETED,
    "rename from ": ChangeKind.RENAMED,
    "copy from ": ChangeKind.ADDED,
}
_NEW_PATH_PREFIXES = ("rename to ", "copy to ")
_OLD_PATH_PREFIXES = ("rename from ", "copy from ")


@dataclass
class _FileHeader:
    """What the extended header lines of one file's diff say, as they are read."""

    change_kind: ChangeKind = ChangeKind.MODIFIED
    old_path: str | None = None
    new_path: str | None = None
    is_binary: bool = False
    new_blob_hash: str | None = None


@dataclass
class _ChangedRun:
    """Changed lines next to one another in a hunk, as they are read.

    old_start and new_start are the numbers of the lines, before and after
    the change, that the run starts at.
    """

    old_start: int
    new_start: int
    removed_lines: list[str]
    added_lines: list[str]

    def build_hunk(self) -> GitHunk:
        """Return the run as ``git diff --unified=0`` gives it."""
        old_count = len(self.removed_lines)
        new_count = len(self.added_lines)
        return GitHunk(
            header=HunkHeader(
                # A side with no lines names the line before the run.
                old_start=self.old_start if old_count else self.old_start - 1,
                old_line_count=old_count,
                new_start=self.new_start if new_count else self.new_start - 1,
                new_line_count=new_count,
            ),
            removed_lines=tuple(self.removed_lines),
            added_lines=tuple(self.added_lines),
        )


def parse_git_diff(diff_text: str) -> list[GitFileChange]:
    """Return each file the diff in ``diff_text`` changes, in the diff's order.

    Raises ValueError, naming the line, when the text is not such a diff,
    or is a combined diff of a merge.
    """
    lines = diff_text.split("\n")
    file_changes: list[GitFileChange] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(_COMBINED_HEADER_PREFIXES):
            raise _build_error(
                "it is a combined diff, as git writes for a merge, and only a "
                "diff against one side can be audited",
                index,
            )
        if not line.startswith(_FILE_HEADER_PREFIX):
            if line:
                raise _build_error(f"the line '{line}' is outside any file", index)
            index += 1
            continue
        file_change, index = _parse_file(lines, index)
        file_changes.append(file_change)
    return file_changes


def _parse_file(lines: list[str], start: int) -> tuple[GitFileChange, int]:
    """Return the file whose diff starts at ``lines[start]``, and where it ends."""
    paths_text = lines[start].removeprefix(_FILE_HEADER_PREFIX)
    header = _FileHeader()
    index = start + 1
    while index < len(lines) and not lines[index].startswith(
        (_FILE_HEADER_PREFIX, _HUNK_HEADER_PREFIX, *_COMBINED_HEADER_PREFIXES)
    ):
        try:
            _read_header_line(lines[index], header)
        except ValueError as error:
            raise _build_error(str(error), index) from error
        index += 1
    hunks: list[GitHunk] = []
    while index < len(lines) and lines[index].startswith(_HUNK_HEADER_PREFIX):
        hunks_of_header, index = _parse_hunk(lines, index)
        hunks.extend(hunks_of_header)
    path = header.new_path or _find_path(paths_text, start)
    return (
        GitFileChange(
            path=path,
            change_kind=header.change_kind,
            hunks=tuple(hunks),
            old_path=header.old_path,
            is_binary=header.is_binary,
            new_blob_hash=header.new_blob_hash,
        ),
        index,
    )


def _find_path(paths_text: str, line_index: int) -> str:
    try:
        path = find_path_of_unrenamed_file(paths_text)
    except ValueError as error:
        raise _build_error(str(error), line_index) from error
    if path is None:
        raise _build_error(
            f"the paths of '{_FILE_HEADER_PREFIX}{paths_text}' differ", line_index
        )
    return path


def _read_header_line(line: str, header: _FileHeader) -> None:
    """Take what one extended header line says about the file into ``header``."""
    for prefix, change_kind in _HEADER_PREFIX_TO_KIND.items():
        if line.startswith(prefix):
            header.change_kind = change_kind
    if line.startswith(_OLD_PATH_PREFIXES):
        header.old_path = unquote_path(line.split(" ", 2)[2])
    elif line.startswith(_NEW_PATH_PREFIXES):
        header.new_path = unquote_path(line.split(" ", 2)[2])
    elif line.startswith(_INDEX_PREFIX):
        # "index <old>..<new>", then the mode when it is the same on both sides.
        hashes = line.removeprefix(_INDEX_PREFIX).split(" ", 1)[0]
        header.new_blob_hash = hashes.partition("..")[2] or None
    elif line.startswith("Binary files ") or line == "GIT binary patch":
        header.is_binary = True


def _parse_hunk(lines: list[str], start: int) -> tuple[list[GitHunk], int]:
    """Return the runs of changed lines in the hunk whose header is ``lines[start]``.

    Also returns where the line after the hunk is.
    """
    try:
        hunk_header = parse_hunk_header(lines[start])
    except ValueError as error:
        raise _build_error(str(error), start) from error
    old_left = hunk_header.old_line_count
    new_left = hunk_header.new_line_count
    # A side with no lines names the line before the hunk.
    old_line = hunk_header.old_start + (0 if old_left else 1)
    new_line = hunk_header.new_start + (0 if new_left else 1)
    runs: list[_ChangedRun] = []
    run: _ChangedRun | None = None
    index = start + 1
    while old_left or new_left:
        if index >= len(lines):
            raise _build_error(f"the hunk '{lines[start]}' ends early", start)
        line = lines[index]
        marker, text = line[:1], line[1:]
        if marker == "-" and old_left:
            run = run or _start_run(runs, old_line, new_line)
            run.removed_lines.append(text)
            old_line, old_left = old_line + 1, old_left - 1
        elif marker == "+" and new_left:
            run = run or _start_run(runs, old_line, new_line)
            run.added_lines.append(text)
            new_line, new_left = new_line + 1, new_left - 1
        elif marker in (" ", "") and old_left and new_left:
            # A line of context; some tools drop the space of an empty one.
            run = None
            old_line, old_left = old_line + 1, old_left - 1
            new_line, new_left = new_line + 1, new_left - 1
        elif marker != _NO_NEWLINE_MARKER_PREFIX:
            raise _build_error(
                f"the line '{line}' of the hunk '{lines[start]}' is not one it counts",
                index,
            )
        index += 1
    while index < len(lines) and lines[index].startswith(_NO_NEWLINE_MARKER_PREFIX):
        index += 1
    return [changed_run.build_hunk() for changed_run in runs], index


def _start_run(runs: list[_ChangedRun], old_line: int, new_line: int) -> _ChangedRun:
    """Return a new run starting at the two lines, added to ``runs``."""
    run = _ChangedRun(old_line, new_line, [], [])
    runs.append(run)
    return run


def _build_error(problem: str, line_index: int) -> ValueError:
    return ValueError(f"Cannot read the diff: line {line_index + 1}: {problem}")
