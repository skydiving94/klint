import asyncio
from pathlib import Path
from typing import List
from src.core.domain.enums import UnitType
from src.core.domain.models import AuditableUnit
from src.core.interfaces.extractor import BaseUnitExtractor


class WholeFileExtractor(BaseUnitExtractor):
    async def extract(self, target: str | Path) -> List[AuditableUnit]:
        path = Path(target)
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        line_count = len(content.splitlines())

        return [
            AuditableUnit(
                unit_id=str(path),
                unit_type=UnitType.FILE,
                content=content,
                file_path=str(path),
                start_line=1,
                end_line=line_count,
            )
        ]
