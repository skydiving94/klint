"""Scanning an audit target: the tree of directories and files that is found."""

from pathlib import Path

import pytest

from klint.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.catalog.common.scanners.target_scanner import TargetScanner
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.klint_warning import KlintWarning
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.scanned_tree import ScannedDirectory
from tests.support.builders import MakeUnreadable, write_text

SCANNER = TargetScanner(
    ExtensionFileTraitsIdentifier({".py": "python", ".ts": "typescript"}),
    IgnoredNames(
        directory_names=frozenset({"build", "node_modules"}),
        file_names=frozenset({"secrets.env"}),
        file_suffixes=frozenset({".lock"}),
    ),
)


class RecordingScanProgressListener(BaseScanProgressListener):
    """Keeps the directories the scanner reports, in the order it reports them."""

    def __init__(self) -> None:
        self.reported_directories: list[Path] = []

    def report_directory_scanned(self, directory: Path) -> None:
        self.reported_directories.append(directory)


def _list_file_paths(root: ScannedDirectory) -> list[str]:
    """Return the path of every file in the tree, relative to its root."""
    return [file.path.relative_to(root.path).as_posix() for file in root.yield_files()]


def _list_directory_paths(root: ScannedDirectory) -> list[str]:
    """Return the path of every directory in the tree, relative to its root."""
    return [
        directory.path.relative_to(root.path).as_posix()
        for directory in root.yield_directories()
    ]


def test_scan_directory_returns_the_tree_with_the_traits_of_each_file(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "a.py", "x = 1\n")
    write_text(tmp_path / "notes.txt", "hello\n")
    write_text(tmp_path / "ui" / "b.ts", "let y = 2;\n")

    root = SCANNER.scan_directory(tmp_path)

    (ui,) = root.subdirectories
    assert (root.path, root.parent) == (tmp_path, None)
    assert [(file.path.name, file.traits.language) for file in root.files] == [
        ("a.py", "python"),
        ("notes.txt", None),
    ]
    assert all(file.parent is root for file in root.files)
    assert ui.path == tmp_path / "ui"
    assert ui.parent is root
    assert [(file.path.name, file.traits.language) for file in ui.files] == [
        ("b.ts", "typescript")
    ]


def test_scan_directory_leaves_out_ignored_names_below_the_target_only(
    tmp_path: Path,
) -> None:
    # The target sits under a folder with an ignored name, which does not count.
    target = tmp_path / "build" / "project"
    write_text(target / "kept.py", "")
    write_text(target / "secrets.env", "")
    write_text(target / "deps.LOCK", "")
    write_text(target / "node_modules" / "dep.py", "")
    write_text(target / "src" / "build" / "output.py", "")
    write_text(target / "src" / "kept_too.py", "")

    root = SCANNER.scan_directory(target)

    assert _list_file_paths(root) == ["kept.py", "src/kept_too.py"]
    assert _list_directory_paths(root) == [".", "src"]


def test_files_and_directories_are_yielded_in_path_order(tmp_path: Path) -> None:
    for relative_path in ("b.py", "a-b.py", "a/z.py", "c/d/e.py"):
        write_text(tmp_path / relative_path, "")

    root = SCANNER.scan_directory(tmp_path)

    # The files of a directory come where the name of the directory sorts.
    assert _list_file_paths(root) == ["a/z.py", "a-b.py", "b.py", "c/d/e.py"]
    assert _list_directory_paths(root) == [".", "a", "c", "c/d"]


def test_scan_directory_does_not_follow_a_link_to_a_directory(tmp_path: Path) -> None:
    target = tmp_path / "project"
    write_text(target / "a.py", "")
    write_text(tmp_path / "elsewhere" / "b.py", "")
    (target / "link").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    (target / "loop").symlink_to(target, target_is_directory=True)

    root = SCANNER.scan_directory(target)

    assert _list_file_paths(root) == ["a.py"]
    assert _list_directory_paths(root) == ["."]


def test_scan_directory_reports_each_scanned_directory_once_in_path_order(
    tmp_path: Path,
) -> None:
    for relative_path in ("top.py", "b/c/y.py", "a/x.py", "build/z.py"):
        write_text(tmp_path / relative_path, "")
    listener = RecordingScanProgressListener()

    SCANNER.scan_directory(tmp_path, listener)

    reported = [
        directory.relative_to(tmp_path).as_posix()
        for directory in listener.reported_directories
    ]
    # The target comes first. A directory with an ignored name is not scanned.
    assert reported == [".", "a", "b", "b/c"]


def test_scan_directory_leaves_out_a_directory_that_cannot_be_read_with_a_warning(
    tmp_path: Path,
    make_unreadable: MakeUnreadable,
) -> None:
    write_text(tmp_path / "a.py", "")
    locked = make_unreadable(write_text(tmp_path / "locked" / "b.py", "").parent)
    listener = RecordingScanProgressListener()

    with pytest.warns(KlintWarning) as caught:
        root = SCANNER.scan_directory(tmp_path, listener)

    assert [str(warning.message) for warning in caught] == [
        f"Directory '{locked}' is left out: it cannot be read (Permission denied)"
    ]
    assert _list_file_paths(root) == ["a.py"]
    assert _list_directory_paths(root) == ["."]
    assert listener.reported_directories == [tmp_path]


def test_scan_directory_gives_an_empty_tree_for_a_target_that_cannot_be_read(
    tmp_path: Path,
    make_unreadable: MakeUnreadable,
) -> None:
    target = make_unreadable(write_text(tmp_path / "project" / "a.py", "").parent)

    with pytest.warns(KlintWarning, match="is left out: it cannot be read"):
        root = SCANNER.scan_directory(target)

    assert (root.path, root.files, root.subdirectories) == (target, [], [])


def test_scan_file_returns_the_file_with_its_traits_and_no_parent(
    tmp_path: Path,
) -> None:
    target = write_text(tmp_path / "a.py", "x = 1\n")

    scanned_file = SCANNER.scan_file(target)

    assert (scanned_file.path, scanned_file.traits.language) == (target, "python")
    assert scanned_file.parent is None
