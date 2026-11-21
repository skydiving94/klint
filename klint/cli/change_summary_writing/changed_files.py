"""The change an agent summarizes, read from git, and its files as klint lists them."""

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from klint.catalog.domain_neutral.git import GitChange, GitChangeSource, GitFileChange

# Where the agent writes its summaries, relative to the project directory.
SUMMARIES_PATH = Path(".klint/change-summary.json")


@dataclass(frozen=True)
class ListedFile:
    """A changed file as klint lists it for the agent to summarize.

    kind_description says how the file changed, such as "renamed from
    app/old.py, binary". hunk_headers are its hunks' headers as
    ``git diff -U0`` writes them; a binary file, or a rename with no edits,
    has none.
    """

    path: str
    kind_description: str
    hunk_headers: tuple[str, ...]


async def read_change_to_summarize(source: GitChangeSource) -> GitChange:
    """Return the change ``source`` reads, without the summaries file.

    The summaries file is left out, as klint leaves a summaries document out
    of the change it checks the document against.
    """
    change = await source.read_input()
    summaries_path = SUMMARIES_PATH.resolve()
    repository_path = change.repository_path.resolve()
    if not summaries_path.is_relative_to(repository_path):
        return change
    relative_path = summaries_path.relative_to(repository_path).as_posix()
    return dataclasses.replace(
        change,
        files=tuple(
            file
            for file in change.files
            if relative_path not in (file.path, file.old_path)
        ),
    )


def list_changed_files(change: GitChange) -> list[ListedFile]:
    """Return each file of ``change``, in the change's order, as klint lists it."""
    return [_list_file(file) for file in change.files]


def _list_file(file: GitFileChange) -> ListedFile:
    kind = file.change_kind.value
    if file.old_path is not None:
        kind = f"{kind} from {file.old_path}"
    if file.is_binary:
        kind = f"{kind}, binary"
    return ListedFile(
        path=file.path,
        kind_description=kind,
        hunk_headers=tuple(hunk.header.format_text() for hunk in file.hunks),
    )
