import asyncio
from pathlib import Path

from src.catalog.common.units.file import AuditableFileUnit
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from src.core.models.unit import AuditableUnit


class WholeFileExtractor(BaseUnitExtractor):
    """Reads a whole file as one unit, marked with the file's identified language."""

    def __init__(self, file_traits_identifier: BaseFileTraitsIdentifier) -> None:
        self._file_traits_identifier = file_traits_identifier

    async def extract(self, target: str | Path) -> list[AuditableUnit]:
        unit = await asyncio.to_thread(self._read_file_sync, Path(target))
        return [unit]

    def _read_file_sync(self, path: Path) -> AuditableFileUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        return AuditableFileUnit(
            unit_id=str(path),
            language=self._file_traits_identifier.identify(path).language,
            content=content,
            file_path=str(path),
            start_line=1,
            end_line=line_count,
        )
