"""The klint-ack command: records that a logged finding is wrong, with a note."""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app.acknowledgements import (
    find_repository_root,
    format_timestamp_now,
    open_acknowledgement_log,
)
from klint.catalog.domain_neutral.git.git_command import run_git
from klint.cli.exit_code import ExitCode

ACKNOWLEDGE_COMMAND_NAME = "klint-ack"


async def acknowledge_entry(argv: Sequence[str], working_directory: Path) -> ExitCode:
    """Acknowledge the entry ``argv`` names in the repository of ``working_directory``.

    The entry file is rewritten and staged, so that the next commit carries
    it. Exits with RUN_ERROR, saying why, when there is no such open entry
    or the log cannot be used.
    """
    parser = argparse.ArgumentParser(
        prog=ACKNOWLEDGE_COMMAND_NAME,
        description=(
            "klint - acknowledges a finding of the pre-commit check as wrong, in "
            "the repository's acknowledgement log, so that it no longer blocks "
            "the commit while the code it is on stays the same"
        ),
    )
    parser.add_argument("entry_id", help="The ID klint-pre-commit printed")
    parser.add_argument(
        "--note", required=True, help="Why the finding is wrong; it is recorded"
    )
    namespace = parser.parse_args(argv)
    entry_id: str = namespace.entry_id
    note: str = namespace.note
    if not note.strip():
        return _fail("the note must say why the finding is wrong")
    repository_root = await find_repository_root(working_directory)
    if repository_root is None:
        return _fail(f"'{working_directory}' is not in a git repository")
    log = open_acknowledgement_log(repository_root)
    try:
        entry = log.find_entry(entry_id)
    except ValueError as error:
        return _fail(error)
    if entry is None:
        return _fail(
            f"there is no entry '{entry_id}' in {log.folder}; the IDs are those "
            "klint-pre-commit prints"
        )
    if not entry.is_open():
        return _fail(f"entry '{entry_id}' is already acknowledged: {entry.note}")
    path = log.write_entry(entry.acknowledge(note.strip(), format_timestamp_now()))
    relative_path = path.relative_to(repository_root)
    output = await run_git(["add", "--", str(relative_path)], repository_root)
    if output.return_code == 0:
        staged_note = f"; staged {relative_path.as_posix()}"
    else:
        staged_note = (
            f"; {relative_path.as_posix()} could not be staged: {output.stderr.strip()}"
        )
    print(
        f"[{ACKNOWLEDGE_COMMAND_NAME}] Acknowledged {entry_id}: {entry.rule_id} on "
        f"{entry.unit.describe()}{staged_note}"
    )
    return ExitCode.NO_PROBLEMS


def run_acknowledge() -> int:
    return asyncio.run(acknowledge_entry(sys.argv[1:], Path.cwd()))


def _fail(reason: Exception | str) -> ExitCode:
    print(f"[{ACKNOWLEDGE_COMMAND_NAME}] Error: {reason}", file=sys.stderr)
    return ExitCode.RUN_ERROR
