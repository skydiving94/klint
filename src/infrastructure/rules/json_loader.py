import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.domain.enums import QuestionType
from src.core.domain.rule import AuditRule
from src.core.domain.units import AuditableUnit
from src.core.interfaces.rule_loader import BaseRuleLoader


class JsonRuleLoader(BaseRuleLoader):
    def __init__(self, default_rules_path: Path):
        self._default_rules_path = default_rules_path
        self._cached_default_rules: Optional[Dict[str, AuditRule]] = None

    async def load_rules(self, custom_rules_source: Optional[Path | str] = None) -> List[AuditRule]:
        return await asyncio.to_thread(self._load_rules_sync, custom_rules_source)

    def _load_rules_sync(self, custom_rules_source: Optional[Path | str] = None) -> List[AuditRule]:
        if self._cached_default_rules is None:
            self._cached_default_rules = (
                self._load_from_path_sync(self._default_rules_path)
                if self._default_rules_path.exists()
                else {}
            )

        merged: Dict[str, AuditRule] = dict(self._cached_default_rules)
        if custom_rules_source is not None:
            merged.update(self._load_from_path_sync(Path(custom_rules_source)))

        return list(merged.values())

    def _load_from_path_sync(self, path: Path) -> Dict[str, AuditRule]:
        raw_data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        rules: Dict[str, AuditRule] = {}
        for rule_id, spec in raw_data.items():
            kwargs: Dict[str, Any] = dict(
                rule_id=rule_id,
                question_type=QuestionType(spec["type"]),
                instructions=spec["instructions"],
            )
            if "target_unit_types" in spec:
                kwargs["target_unit_types"] = self._validate_unit_types(
                    spec["target_unit_types"], rule_id)
            rules[rule_id] = AuditRule(**kwargs)
        return rules

    def _validate_unit_types(self, raw_types: List[str], rule_id: str) -> List[str]:
        known = set(AuditableUnit.known_unit_types())
        unknown = [t for t in raw_types if t not in known]
        if unknown:
            raise ValueError(
                f"Rule '{rule_id}' has unknown target_unit_types {unknown}; known: {sorted(known)}")
        return list(raw_types)
