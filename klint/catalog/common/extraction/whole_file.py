import asyncio

from klint.catalog.common.extraction.dispatched_file import DispatchedFile
from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.unit import AuditableUnit


class WholeFileExtractor(BaseUnitExtractor[DispatchedFile]):
    """Reads a whole file as one unit, in the language its traits give.

    A binary file gives no unit.
    """

    async def extract(self, audit_input: DispatchedFile) -> list[AuditableUnit]:
        if audit_input.is_binary:
            return []
        return await asyncio.to_thread(self._read_file_sync, audit_input)

    def _read_file_sync(self, dispatched_file: DispatchedFile) -> list[AuditableUnit]:
        path = dispatched_file.path
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        return [
            AuditableFileUnit(
                unit_id=str(path),
                traits=dispatched_file.traits,
                content=content,
                file_path=str(path),
                start_line=1,
                end_line=line_count,
            )
        ]
