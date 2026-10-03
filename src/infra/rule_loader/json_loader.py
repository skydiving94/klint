import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.models.question_type import QuestionType
from src.core.models.rule import AuditRule
from src.core.models.unit import AuditableUnit
from src.core.interfaces.rule_loader import BaseRuleLoader


class JsonRuleLoader(BaseRuleLoader):
    def __init__(self, default_rules_path: Path):
        self._default_rules_path = default_rules_path
        self._cached_default_rules: Optional[Dict[str, AuditRule]] = None
        self._cached_custom_rules: Dict[Path, Dict[str, AuditRule]] = {}
        self._lock = asyncio.Lock()

    async def load_rules(
        self, custom_rules_source: Optional[Path | str] = None
    ) -> List[AuditRule]:
        async with self._lock:
            if self._cached_default_rules is None:
                self._cached_default_rules = await asyncio.to_thread(
                    self._load_default_rules_sync
                )
            if custom_rules_source is None:
                return list(self._cached_default_rules.values())

            custom_path = Path(custom_rules_source).resolve()
            if custom_path not in self._cached_custom_rules:
                self._cached_custom_rules[custom_path] = (
                    await asyncio.to_thread(
                        self._load_custom_rules_sync, custom_path
                    )
                )
            custom_rules = self._cached_custom_rules[custom_path]

        merged: Dict[str, AuditRule] = dict(self._cached_default_rules)
        merged.update(custom_rules)
        return list(merged.values())

    def _load_default_rules_sync(self) -> Dict[str, AuditRule]:
        if not self._default_rules_path.exists():
            return {}
        return self._load_from_path_sync(self._default_rules_path)

    def _load_custom_rules_sync(self, path: Path) -> Dict[str, AuditRule]:
        if not path.is_file():
            raise FileNotFoundError(
                f"Custom rules file does not exist: {path}")
        return self._load_from_path_sync(path)

    def _load_from_path_sync(self, path: Path) -> Dict[str, AuditRule]:
        raw_data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        # Support both flat rule JSON files and ESLint-style {"env": {...}, "rules": {...}} configs
        rules_block = (
            raw_data["rules"]
            if isinstance(raw_data.get("rules"), dict)
            and "type" not in raw_data["rules"]
            else raw_data
        )
        rules: Dict[str, AuditRule] = {}
        for rule_id, spec in rules_block.items():
            if (
                not isinstance(spec, dict)
                or "type" not in spec
                or "instructions" not in spec
            ):
                continue
            kwargs: Dict[str, Any] = dict(
                rule_id=rule_id,
                question_type=QuestionType(spec["type"]),
                instructions=spec["instructions"],
            )
            if "target_unit_types" in spec:
                kwargs["target_unit_types"] = self._validate_unit_types(
                    spec["target_unit_types"], rule_id
                )
            rules[rule_id] = AuditRule(**kwargs)
        return rules

    def _validate_unit_types(
        self, raw_types: List[str], rule_id: str
    ) -> List[str]:
        known = set(AuditableUnit.known_unit_types())
        unknown = [t for t in raw_types if t not in known]
        if unknown:
            raise ValueError(
                f"Rule '{rule_id}' has unknown target_unit_types {unknown}; known: {sorted(known)}"
            )
        return list(raw_types)
