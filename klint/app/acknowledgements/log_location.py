"""Where a repository keeps its acknowledgement log."""

from pathlib import Path

from klint.catalog.domain_neutral.git.git_command import run_git
from klint.infra.acknowledgement_log import FileAcknowledgementLog

# The log's folder, from the repository's root.
ACKNOWLEDGEMENTS_FOLDER = Path(".klint") / "acknowledgements"


async def find_repository_root(directory: Path) -> Path | None:
    """Return the root of the git repository ``directory`` is in; None when none.

    None too when git cannot be run.
    """
    try:
        output = await run_git(["rev-parse", "--show-toplevel"], directory)
    except ValueError:
        return None
    if output.return_code != 0:
        return None
    return Path(output.stdout.strip())


def open_acknowledgement_log(repository_root: Path) -> FileAcknowledgementLog:
    """Return the log of the repository at ``repository_root``."""
    return FileAcknowledgementLog(repository_root / ACKNOWLEDGEMENTS_FOLDER)
