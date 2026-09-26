import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.domain.models import AuditRule
from src.core.interfaces.rule_loader import BaseRuleLoader


class JsonRuleLoader(BaseRuleLoader):
    def __init__(self, default_rules_path: Path):
        self._default_rules_path = default_rules_path

    async def load_rules(self, custom_rules_source: Optional[Path | str] = None) -> List[AuditRule]:
        merged: Dict[str, AuditRule] = {}

        if self._default_rules_path.exists():
            merged.update(await self._load_from_path(self._default_rules_path))

        if custom_rules_source is not None:
            merged.update(await self._load_from_path(Path(custom_rules_source)))

        return list(merged.values())

    async def _load_from_path(self, path: Path) -> Dict[str, AuditRule]:
        raw_text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        raw_data: Dict[str, Any] = json.loads(raw_text)
        return {
            rule_id: AuditRule(
                rule_id=rule_id,
                question_type=spec["type"],
                instructions=spec["instructions"],
                criteria=spec["criteria"],
            )
            for rule_id, spec in raw_data.items()
        }
