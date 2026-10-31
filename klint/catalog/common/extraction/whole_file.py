import asyncio

from klint.catalog.common.extraction.binary_check import is_likely_binary
from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.scanned_tree import ScannedFile
from klint.core.models.unit import AuditableUnit


class WholeFileExtractor(BaseUnitExtractor[ScannedFile]):
    """Reads a whole file as one unit, in the language its traits give.

    A binary file gives no unit.
    """

    async def extract(self, audit_input: ScannedFile) -> list[AuditableUnit]:
        return await asyncio.to_thread(self._read_file_sync, audit_input)

    def _read_file_sync(self, scanned_file: ScannedFile) -> list[AuditableUnit]:
        path = scanned_file.path
        if is_likely_binary(path):
            return []
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        return [
            AuditableFileUnit(
                unit_id=str(path),
                traits=scanned_file.traits,
                content=content,
                file_path=str(path),
                start_line=1,
                end_line=line_count,
            )
        ]
