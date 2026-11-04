"""Reads the patch git's diff writes, with no lines of context, into changed files.

The diff is expected as ``git diff --unified=0 --src-prefix=a/ --dst-prefix=b/``
writes it, with copies not detected.
"""

from dataclasses import dataclass

from klint.catalog.domain_neutral.git.git_change import (
    ChangeKind,
    GitFileChange,
    GitHunk,
    parse_hunk_header,
)

_FILE_HEADER_PREFIX = "diff --git "
_HUNK_HEADER_PREFIX = "@@ "
_RENAME_FROM_PREFIX = "rename from "
_RENAME_TO_PREFIX = "rename to "
_NO_NEWLINE_MARKER_PREFIX = "\\"
_SOURCE_PREFIX = "a/"
_DESTINATION_PREFIX = "b/"
# The escapes git uses in a quoted path, other than three octal digits.
_ESCAPE_TO_BYTE = {
    "a": 0x07,
    "b": 0x08,
    "t": 0x09,
    "n": 0x0A,
    "v": 0x0B,
    "f": 0x0C,
    "r": 0x0D,
    '"': 0x22,
    "\\": 0x5C,
}


@dataclass
class _FileHeader:
    """What the extended header lines of one file's diff say, as they are read."""

    change_kind: ChangeKind = ChangeKind.MODIFIED
    old_path: str | None = None
    new_path: str | None = None
    is_binary: bool = False


def parse_git_diff(diff_text: str) -> list[GitFileChange]:
    """Return each file the diff in ``diff_text`` changes, in the diff's order.

    Raises ValueError when the text is not such a diff.
    """
    lines = diff_text.split("\n")
    file_changes: list[GitFileChange] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith(_FILE_HEADER_PREFIX):
            if lines[index]:
                raise _build_error(f"the line '{lines[index]}' is outside any file")
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
        (_FILE_HEADER_PREFIX, _HUNK_HEADER_PREFIX)
    ):
        _read_header_line(lines[index], header)
        index += 1
    hunks: list[GitHunk] = []
    while index < len(lines) and lines[index].startswith(_HUNK_HEADER_PREFIX):
        hunk, index = _parse_hunk(lines, index)
        hunks.append(hunk)
    path = header.new_path or _find_path_of_unrenamed_file(paths_text)
    return (
        GitFileChange(
            path=path,
            change_kind=header.change_kind,
            hunks=tuple(hunks),
            old_path=header.old_path,
            is_binary=header.is_binary,
        ),
        index,
    )


def _read_header_line(line: str, header: _FileHeader) -> None:
    """Take what one extended header line says about the file into ``header``."""
    if line.startswith("new file mode "):
        header.change_kind = ChangeKind.ADDED
    elif line.startswith("deleted file mode "):
        header.change_kind = ChangeKind.DELETED
    elif line.startswith(_RENAME_FROM_PREFIX):
        header.change_kind = ChangeKind.RENAMED
        header.old_path = _unquote_path(line.removeprefix(_RENAME_FROM_PREFIX))
    elif line.startswith(_RENAME_TO_PREFIX):
        header.new_path = _unquote_path(line.removeprefix(_RENAME_TO_PREFIX))
    elif line.startswith("Binary files ") or line == "GIT binary patch":
        header.is_binary = True


def _parse_hunk(lines: list[str], start: int) -> tuple[GitHunk, int]:
    """Return the hunk whose header is ``lines[start]``, and where the next line is."""
    hunk_header = parse_hunk_header(lines[start])
    removed_lines: list[str] = []
    added_lines: list[str] = []
    index = start + 1
    while (
        len(removed_lines) < hunk_header.old_line_count
        or len(added_lines) < hunk_header.new_line_count
    ):
        if index >= len(lines):
            raise _build_error(f"the hunk '{lines[start]}' ends early")
        line = lines[index]
        if line.startswith("-") and len(removed_lines) < hunk_header.old_line_count:
            removed_lines.append(line[1:])
        elif line.startswith("+") and len(added_lines) < hunk_header.new_line_count:
            added_lines.append(line[1:])
        elif not line.startswith(_NO_NEWLINE_MARKER_PREFIX):
            raise _build_error(
                f"the line '{line}' of the hunk '{lines[start]}' is not one it counts"
            )
        index += 1
    while index < len(lines) and lines[index].startswith(_NO_NEWLINE_MARKER_PREFIX):
        index += 1
    return (
        GitHunk(
            header=hunk_header,
            removed_lines=tuple(removed_lines),
            added_lines=tuple(added_lines),
        ),
        index,
    )


def _find_path_of_unrenamed_file(paths_text: str) -> str:
    """Return the path in "a/<path> b/<path>", a file's paths when it keeps its name."""
    if paths_text.startswith('"'):
        source_path, rest = _read_quoted_text(paths_text)
        destination_path = _unquote_path(rest.removeprefix(" "))
    else:
        half_length = (len(paths_text) - 1) // 2
        source_path = paths_text[:half_length]
        destination_path = paths_text[half_length + 1 :]
    if (
        not source_path.startswith(_SOURCE_PREFIX)
        or not destination_path.startswith(_DESTINATION_PREFIX)
        or source_path.removeprefix(_SOURCE_PREFIX)
        != destination_path.removeprefix(_DESTINATION_PREFIX)
    ):
        raise _build_error(f"the paths of '{_FILE_HEADER_PREFIX}{paths_text}' differ")
    return destination_path.removeprefix(_DESTINATION_PREFIX)


def _unquote_path(text: str) -> str:
    """Return the path ``text`` holds, quoted as git quotes an unusual path or not."""
    if not text.startswith('"'):
        return text
    path, rest = _read_quoted_text(text)
    if rest:
        raise _build_error(f"the quoted path {text} is followed by '{rest}'")
    return path


def _read_quoted_text(text: str) -> tuple[str, str]:
    """Return the text quoted at the start of ``text``, unescaped, and what follows.

    The quoted text is read as git writes it: C escapes, and any other byte
    as three octal digits.
    """
    path_bytes = bytearray()
    index = 1
    while index < len(text):
        character = text[index]
        if character == '"':
            return path_bytes.decode("utf-8", errors="replace"), text[index + 1 :]
        if character != "\\":
            path_bytes.extend(character.encode("utf-8"))
            index += 1
            continue
        escape = text[index + 1 : index + 2]
        if escape in _ESCAPE_TO_BYTE:
            path_bytes.append(_ESCAPE_TO_BYTE[escape])
            index += 2
        elif text[index + 1 : index + 4].isdigit():
            path_bytes.append(int(text[index + 1 : index + 4], 8))
            index += 4
        else:
            raise _build_error(f"the quoted path {text} has an unknown escape")
    raise _build_error(f"the quoted path {text} has no closing quote")


def _build_error(problem: str) -> ValueError:
    return ValueError(f"Cannot read git's diff: {problem}")
