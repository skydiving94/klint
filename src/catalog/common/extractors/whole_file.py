import asyncio
from pathlib import Path
from typing import List

from src.catalog.common.units.file import AuditableFileUnit
from src.core.models.unit import AuditableUnit
from src.core.interfaces.extractor import BaseUnitExtractor


class WholeFileExtractor(BaseUnitExtractor):
    async def extract(self, target: str | Path) -> List[AuditableUnit]:
        unit = await asyncio.to_thread(self._read_file_sync, Path(target))
        return [unit]

    def _read_file_sync(self, path: Path) -> AuditableFileUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(content.splitlines())
        return AuditableFileUnit(
            unit_id=str(path),
            content=content,
            file_path=str(path),
            start_line=1,
            end_line=line_count,
        )
