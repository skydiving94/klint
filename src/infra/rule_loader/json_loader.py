import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src.core.interfaces.rule_loader import BaseRuleLoader
from src.core.models.question_type import QuestionType
from src.core.models.rule import AuditRule
from src.core.registry import UnitRegistry


class JsonRuleLoader(BaseRuleLoader):
    def __init__(
        self, default_rules_paths: Sequence[Path], unit_registry: UnitRegistry
    ):
        self._unit_registry = unit_registry
        self._default_rules_paths: list[Path] = list(default_rules_paths)
        self._cached_default_rules: dict[str, AuditRule] | None = None
        self._cached_custom_rules: dict[Path, dict[str, AuditRule]] = {}
        self._lock = asyncio.Lock()

    async def load_rules(
        self, custom_rules_source: Path | str | None = None
    ) -> list[AuditRule]:
        async with self._lock:
            if self._cached_default_rules is None:
                self._cached_default_rules = await asyncio.to_thread(
                    self._load_default_rules_sync
                )
            if custom_rules_source is None:
                return list(self._cached_default_rules.values())

            custom_path = Path(custom_rules_source).resolve()
            if custom_path not in self._cached_custom_rules:
                self._cached_custom_rules[custom_path] = await asyncio.to_thread(
                    self._load_custom_rules_sync, custom_path
                )
            custom_rules = self._cached_custom_rules[custom_path]

        merged: dict[str, AuditRule] = dict(self._cached_default_rules)
        merged.update(custom_rules)
        return list(merged.values())

    def _load_default_rules_sync(self) -> dict[str, AuditRule]:
        """Load every default pack in order; a later pack overrides an earlier one by rule ID."""
        rules: dict[str, AuditRule] = {}
        for path in self._default_rules_paths:
            if path.exists():
                rules.update(self._load_from_path_sync(path))
        return rules

    def _load_custom_rules_sync(self, path: Path) -> dict[str, AuditRule]:
        if not path.is_file():
            raise FileNotFoundError(f"Custom rules file does not exist: {path}")
        return self._load_from_path_sync(path)

    def _load_from_path_sync(self, path: Path) -> dict[str, AuditRule]:
        raw_data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        # Support both flat rule JSON files and ESLint-style {"env": {...}, "rules": {...}} configs
        rules_block = (
            raw_data["rules"]
            if isinstance(raw_data.get("rules"), dict)
            and "type" not in raw_data["rules"]
            else raw_data
        )
        rules: dict[str, AuditRule] = {}
        for rule_id, spec in rules_block.items():
            if (
                not isinstance(spec, dict)
                or "type" not in spec
                or "instructions" not in spec
            ):
                continue
            kwargs: dict[str, Any] = dict(
                rule_id=rule_id,
                question_type=QuestionType(spec["type"]),
                instructions=spec["instructions"],
            )
            if "target_unit_types" in spec:
                kwargs["target_unit_types"] = self._validate_unit_types(
                    spec["target_unit_types"], rule_id
                )
            for field_name in ("languages", "tags"):
                if field_name in spec:
                    kwargs[field_name] = self._validate_string_list(
                        spec[field_name], field_name, rule_id
                    )
            rules[rule_id] = AuditRule(**kwargs)
        return rules

    def _validate_unit_types(self, raw_types: list[str], rule_id: str) -> list[str]:
        known = set(self._unit_registry.known_unit_types())
        unknown = [t for t in raw_types if t not in known]
        if unknown:
            raise ValueError(
                f"Rule '{rule_id}' has unknown target_unit_types {unknown}; known: {sorted(known)}"
            )
        return list(raw_types)

    def _validate_string_list(
        self, raw_value: Any, field_name: str, rule_id: str
    ) -> list[str]:
        if not isinstance(raw_value, list) or not all(
            isinstance(item, str) for item in raw_value
        ):
            raise ValueError(
                f"Rule '{rule_id}' has invalid {field_name} {raw_value!r}; expected a list of strings"
            )
        return list(raw_value)
