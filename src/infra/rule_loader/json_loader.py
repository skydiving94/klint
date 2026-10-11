import asyncio
import json
import warnings
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

from src.core.interfaces.rule_loader import BaseRuleLoader
from src.core.klint_warning import KlintWarning
from src.core.models.question_type import QuestionType
from src.core.models.rule import AuditRule
from src.core.registry import UnitRegistry

_RULE_FIELD_NAMES = frozenset(
    {"type", "instructions", "target_unit_types", "languages", "tags"}
)
# A settings block may sit beside the rules in the same file; it is not a rule.
_ENV_BLOCK_KEY = "env"


class JsonRuleLoader(BaseRuleLoader):
    """Loads rules from JSON files.

    A file that cannot be read as rules stops the load with an error. A
    problem in one rule is reported as a KlintWarning and the load goes on.
    known_languages are the languages a file can be identified as.
    """

    def __init__(
        self,
        default_rules_paths: Sequence[Path],
        unit_registry: UnitRegistry,
        known_languages: Collection[str],
    ) -> None:
        self._unit_registry = unit_registry
        self._known_languages = {language.lower() for language in known_languages}
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
        """Load every default pack in order.

        A later pack overrides an earlier one by rule ID.
        """
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
        try:
            raw_data: object = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(
                f"Rules file '{path}' is not valid JSON: {error}"
            ) from error
        if not isinstance(raw_data, dict):
            raise ValueError(f"Rules file '{path}' must be a JSON object")
        # Support both flat rule JSON files and ESLint-style configs of the form
        # {"env": {...}, "rules": {...}}
        rules_block: dict[str, Any] = (
            raw_data["rules"]
            if isinstance(raw_data.get("rules"), dict)
            and "type" not in raw_data["rules"]
            else {
                key: value for key, value in raw_data.items() if key != _ENV_BLOCK_KEY
            }
        )
        rules: dict[str, AuditRule] = {}
        for rule_id, spec in rules_block.items():
            if (
                not isinstance(spec, dict)
                or "type" not in spec
                or "instructions" not in spec
            ):
                warnings.warn(
                    f"Rule '{rule_id}' in '{path}' is skipped: it needs both "
                    "'type' and 'instructions'",
                    KlintWarning,
                    stacklevel=2,
                )
                continue
            self._validate_field_names(spec, rule_id, path)
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
            rule = AuditRule(**kwargs)
            self._validate_languages(rule.languages, rule_id, path)
            rules[rule_id] = rule
        return rules

    def _validate_field_names(
        self, spec: dict[str, Any], rule_id: str, path: Path
    ) -> None:
        """Warn about fields a rule cannot have; they are ignored."""
        unknown = sorted(set(spec) - _RULE_FIELD_NAMES)
        if unknown:
            warnings.warn(
                f"Rule '{rule_id}' in '{path}' has unknown fields {unknown}, "
                f"which are ignored; known fields: {sorted(_RULE_FIELD_NAMES)}",
                KlintWarning,
                stacklevel=2,
            )

    def _validate_languages(
        self, languages: Sequence[str], rule_id: str, path: Path
    ) -> None:
        """Warn about languages no file can be identified as."""
        unknown = [
            language
            for language in languages
            if language.lower() not in self._known_languages
        ]
        if unknown:
            warnings.warn(
                f"Rule '{rule_id}' in '{path}' names unknown languages {unknown}, "
                "so it never runs for them; known languages: "
                f"{sorted(self._known_languages)}",
                KlintWarning,
                stacklevel=2,
            )

    def _validate_unit_types(self, raw_types: list[str], rule_id: str) -> list[str]:
        known = set(self._unit_registry.known_unit_types())
        unknown = [t for t in raw_types if t not in known]
        if unknown:
            raise ValueError(
                f"Rule '{rule_id}' has unknown target_unit_types {unknown}; "
                f"known: {sorted(known)}"
            )
        return list(raw_types)

    def _validate_string_list(
        self, raw_value: object, field_name: str, rule_id: str
    ) -> list[str]:
        if not isinstance(raw_value, list) or not all(
            isinstance(item, str) for item in raw_value
        ):
            raise ValueError(
                f"Rule '{rule_id}' has invalid {field_name} {raw_value!r}; "
                "expected a list of strings"
            )
        return list(raw_value)
