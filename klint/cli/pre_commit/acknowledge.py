"""The klint-ack command: records that a finding is wrong, with a note."""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from klint.app import AppSettings, BindingOverride
from klint.app.acknowledgements import (
    FindingRebuilding,
    RebuiltFinding,
    find_repository_root,
    format_timestamp_now,
    open_acknowledgement_log,
)
from klint.catalog.code import FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID
from klint.catalog.domain_neutral.git.git_command import run_git
from klint.cli.exit_code import ExitCode
from klint.composition import create_built_in_injector
from klint.core.models.reports import AcknowledgementEntry
from klint.infra.acknowledgement_log import FileAcknowledgementLog

ACKNOWLEDGE_COMMAND_NAME = "klint-ack"


async def acknowledge_entry(
    argv: Sequence[str], working_directory: Path, *binding_overrides: BindingOverride
) -> ExitCode:
    """Acknowledge the finding ``argv`` names, in ``working_directory``'s repository.

    An open entry of the log is acknowledged. An ID with no entry, such as
    one a pull request's review comment gives, is looked for among the
    findings the code as it stands could get, without asking a judge, and
    the one finding with that ID gets a new, acknowledged entry. The entry
    file is written and staged, so that the next commit carries it. Binding
    overrides replace or add bindings of the wiring. Exits with RUN_ERROR,
    saying why, when no finding has the ID, or the log or the code cannot be
    used.
    """
    parser = argparse.ArgumentParser(
        prog=ACKNOWLEDGE_COMMAND_NAME,
        description=(
            "klint - acknowledges a finding of the pre-commit check or of a pull "
            "request's check as wrong, in the repository's acknowledgement log, "
            "so that it no longer fails either while the code it is on stays "
            "the same"
        ),
    )
    parser.add_argument(
        "entry_id",
        help="The ID klint-pre-commit printed, or a pull request's review comment gave",
    )
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
        rebuilt = await _find_rebuilt_finding(
            entry_id, repository_root, working_directory, log, binding_overrides
        )
        if isinstance(rebuilt, str):
            return _fail(rebuilt)
        entry = rebuilt.build_acknowledged_entry(note.strip(), format_timestamp_now())
    elif entry.is_open():
        entry = entry.acknowledge(note.strip(), format_timestamp_now())
    else:
        return _fail(f"entry '{entry_id}' is already acknowledged: {entry.note}")
    return await _stage_entry(log.write_entry(entry), entry, repository_root)


async def _find_rebuilt_finding(
    entry_id: str,
    repository_root: Path,
    working_directory: Path,
    log: FileAcknowledgementLog,
    binding_overrides: Sequence[BindingOverride],
) -> RebuiltFinding | str:
    """Return the one finding the code as it stands could get under ``entry_id``.

    Returns the reason instead when none has it, more than one has it, or
    the code or the settings cannot be read.
    """
    try:
        settings = await asyncio.to_thread(AppSettings.from_env)
        rebuilding = create_built_in_injector(settings, *binding_overrides).get(
            FindingRebuilding
        )
        findings = await rebuilding.find_findings(
            entry_id,
            (FILE_CONTENTS_KIND_ID, PROJECT_STRUCTURE_KIND_ID),
            repository_root,
            working_directory,
        )
    except (OSError, ValueError) as error:
        return f"the findings of the code could not be rebuilt: {error}"
    if not findings:
        return (
            f"there is no entry '{entry_id}' in {log.folder}, and no finding on "
            "the code as it stands has that ID: the code has changed since the "
            "ID was given, or the ID is wrong. A finding given with no ID, as "
            "on a directory, is turned off in klint.json's rule_exclusions"
        )
    if len(findings) > 1:
        return f"'{entry_id}' is the ID of {len(findings)} findings; none was chosen"
    return findings[0]


async def _stage_entry(
    path: Path, entry: AcknowledgementEntry, repository_root: Path
) -> ExitCode:
    """Stage the entry file at ``path``, and say what was acknowledged."""
    relative_path = path.relative_to(repository_root)
    output = await run_git(["add", "--", str(relative_path)], repository_root)
    if output.return_code == 0:
        staged_note = f"; staged {relative_path.as_posix()}"
    else:
        staged_note = (
            f"; {relative_path.as_posix()} could not be staged: {output.stderr.strip()}"
        )
    print(
        f"[{ACKNOWLEDGE_COMMAND_NAME}] Acknowledged {entry.entry_id}: "
        f"{entry.rule_id} on "
        f"{entry.unit.describe()}{staged_note}"
    )
    return ExitCode.NO_PROBLEMS


def run_acknowledge() -> int:
    return asyncio.run(acknowledge_entry(sys.argv[1:], Path.cwd()))


def _fail(reason: Exception | str) -> ExitCode:
    print(f"[{ACKNOWLEDGE_COMMAND_NAME}] Error: {reason}", file=sys.stderr)
    return ExitCode.RUN_ERROR
