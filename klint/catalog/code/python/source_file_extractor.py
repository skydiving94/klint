import ast
import asyncio
import re
import warnings
from collections.abc import Iterator
from pathlib import Path

from klint.catalog.code.python.definition_reader import SourceFile, read_definitions
from klint.catalog.code.python.definition_units import (
    AuditablePythonDefinitionUnit,
)
from klint.catalog.code.python.source_file_unit import AuditablePythonFileUnit
from klint.catalog.domain_neutral.extraction import DispatchedFile
from klint.core import KlintWarning
from klint.core.interfaces import BaseUnitExtractor
from klint.core.models.units import AuditableUnit

# The line breaks the parser numbers lines by.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class PythonSourceFileExtractor(BaseUnitExtractor[DispatchedFile]):
    """Reads a Python file as one unit, and each class and function in it as one.

    The file comes first, then each unit nested in it before the units
    nested inside that one. A binary file gives no unit. A file the parser
    gives up on is still read whole, with a warning, and gives no other
    unit.
    """

    async def extract(self, audit_input: DispatchedFile) -> list[AuditableUnit]:
        if audit_input.is_binary:
            return []
        return await asyncio.to_thread(self._read_file_sync, audit_input)

    def _read_file_sync(self, dispatched_file: DispatchedFile) -> list[AuditableUnit]:
        path = dispatched_file.path
        content = path.read_text(encoding="utf-8", errors="replace")
        file_unit = AuditablePythonFileUnit(
            unit_id=str(path),
            traits=dispatched_file.traits,
            content=content,
            file_path=str(path),
            start_line=1,
            end_line=len(content.splitlines()),
            members=_read_members(dispatched_file, content),
        )
        return list(_yield_unit_and_nested_units(file_unit))


def _read_members(
    dispatched_file: DispatchedFile, content: str
) -> tuple[AuditablePythonDefinitionUnit, ...]:
    """Return the units at the top of the file; none, with a warning, if unparseable."""
    path = dispatched_file.path
    try:
        tree = ast.parse(content, filename=str(path))
    except (SyntaxError, ValueError, MemoryError, RecursionError) as error:
        # The parser reports source nested too deeply for it as a MemoryError
        # or a RecursionError, and a null byte as a ValueError.
        _warn_about_unparseable_file(path, error)
        return ()
    return read_definitions(
        SourceFile(
            path=str(path),
            traits=dispatched_file.traits,
            lines=_LINE_BREAK.split(content),
            tree=tree,
        )
    )


def _yield_unit_and_nested_units(unit: AuditableUnit) -> Iterator[AuditableUnit]:
    """Yield ``unit``, then every unit nested inside it, parents before children."""
    yield unit
    for child in unit.list_children():
        yield from _yield_unit_and_nested_units(child)


def _warn_about_unparseable_file(path: Path, error: Exception) -> None:
    """Warn that the file at ``path`` is judged whole only: it cannot be parsed."""
    if isinstance(error, SyntaxError) and error.msg:
        reason = f"{error.msg}, line {error.lineno}" if error.lineno else error.msg
    else:
        reason = str(error) or type(error).__name__
    warnings.warn(
        f"File '{path}' is judged as a whole only: it cannot be parsed ({reason}), "
        "so its classes and functions are not judged on their own",
        KlintWarning,
        stacklevel=2,
    )
