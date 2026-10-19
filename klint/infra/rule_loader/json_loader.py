import asyncio
import json
import warnings
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.klint_warning import KlintWarning
from klint.core.models.file_traits import FileTraits
from klint.core.models.question_type import QuestionType
from klint.core.models.rule import AuditRule
from klint.core.registry import UnitRegistry

_RULE_FIELD_NAMES = frozenset(
    {"type", "instructions", "target_unit_types", "languages", "tags"}
)
# The header of a pack: which files the pack is for.
_HEADER_KEY = "applies_to"
_HEADER_FIELD_NAMES = frozenset({"languages"})
# Keys that may sit beside the rules in the same file and are not rules: the
# header, and the settings a klint.json holds.
_NON_RULE_KEYS = frozenset({_HEADER_KEY, "env", "fallback_rule_packs"})


@dataclass(frozen=True)
class _PackScope:
    """The files a pack is for, as its header states them.

    languages is None when the pack is not limited to some languages, as for
    a file without a header.
    """

    languages: tuple[str, ...] | None = None

    def matches(self, language: str) -> bool:
        """Return True when the pack is for files written in ``language``."""
        return self.languages is None or language.lower() in self._lowered_languages()

    def narrow(self, rule_languages: Sequence[str]) -> list[str]:
        """Return the languages a rule of this pack is limited to.

        A rule that names no language inherits the pack's; one that does
        keeps those that are also the pack's.
        """
        if self.languages is None:
            return list(rule_languages)
        if not rule_languages:
            return list(self.languages)
        return [
            language
            for language in rule_languages
            if language.lower() in self._lowered_languages()
        ]

    def _lowered_languages(self) -> set[str]:
        return {language.lower() for language in self.languages or ()}


@dataclass(frozen=True)
class _RulePack:
    """A rules file as read: its scope, and its rules not yet checked."""

    path: Path
    scope: _PackScope
    rule_specs: dict[str, Any]


class JsonRuleLoader(BaseRuleLoader):
    """Loads rules from JSON rule packs, choosing the packs by the traits of files.

    A file of an identified language is asked every pack whose applies_to
    header matches its traits; a pack without a header matches every such
    file. A file whose language is not identified is asked the fallback
    packs instead. A rule inherits its pack's languages and may narrow them.
    The rules of a pack are read only once the pack is chosen.

    A file that cannot be read as rules stops the load with an error. A
    problem in one rule is reported as a KlintWarning and the load goes on.
    A pack that does not exist gives no rules. known_languages are the
    languages a file can be identified as.
    """

    def __init__(
        self,
        rule_packs: Sequence[Path],
        fallback_rule_packs: Sequence[Path],
        unit_registry: UnitRegistry,
        known_languages: Collection[str],
    ) -> None:
        self._rule_packs = list(rule_packs)
        self._fallback_rule_packs = list(fallback_rule_packs)
        self._unit_registry = unit_registry
        self._known_languages = {language.lower() for language in known_languages}
        # Each file is read and checked once, however many loads use it.
        self._path_to_pack: dict[Path, _RulePack | None] = {}
        self._path_to_rules: dict[Path, dict[str, AuditRule]] = {}
        self._lock = asyncio.Lock()

    async def load_rules(
        self, traits: FileTraits, custom_rules_source: str | Path | None = None
    ) -> list[AuditRule]:
        custom_path = (
            None if custom_rules_source is None else Path(custom_rules_source).resolve()
        )
        async with self._lock:
            return await asyncio.to_thread(self._load_rules_sync, traits, custom_path)

    def _load_rules_sync(
        self, traits: FileTraits, custom_path: Path | None
    ) -> list[AuditRule]:
        """Merge the chosen packs in order, then the custom rules, by rule ID."""
        rules: dict[str, AuditRule] = {}
        for pack in self._choose_packs(traits):
            rules.update(self._load_pack_rules(pack))
        if custom_path is not None:
            rules.update(self._load_pack_rules(self._read_custom_pack(custom_path)))
        return list(rules.values())

    def _choose_packs(self, traits: FileTraits) -> Iterator[_RulePack]:
        if traits.language is None:
            for path in self._fallback_rule_packs:
                pack = self._read_pack(path)
                if pack is not None:
                    yield pack
            return
        for path in self._rule_packs:
            pack = self._read_pack(path)
            if pack is not None and pack.scope.matches(traits.language):
                yield pack

    def _read_pack(self, path: Path) -> _RulePack | None:
        """Return the pack at ``path``; None when there is no such file."""
        if path not in self._path_to_pack:
            self._path_to_pack[path] = (
                self._read_pack_file(path) if path.exists() else None
            )
        return self._path_to_pack[path]

    def _read_custom_pack(self, path: Path) -> _RulePack:
        if not path.is_file():
            raise FileNotFoundError(f"Custom rules file does not exist: {path}")
        pack = self._read_pack(path)
        assert pack is not None
        return pack

    def _read_pack_file(self, path: Path) -> _RulePack:
        try:
            raw_data: object = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(
                f"Rules file '{path}' is not valid JSON: {error}"
            ) from error
        if not isinstance(raw_data, dict):
            raise ValueError(f"Rules file '{path}' must be a JSON object")
        scope = (
            self._read_scope(raw_data[_HEADER_KEY], path)
            if _HEADER_KEY in raw_data
            else _PackScope()
        )
        # Support both flat rule JSON files and ESLint-style configs of the form
        # {"env": {...}, "rules": {...}}
        rule_specs: dict[str, Any] = (
            raw_data["rules"]
            if isinstance(raw_data.get("rules"), dict)
            and "type" not in raw_data["rules"]
            else {
                key: value
                for key, value in raw_data.items()
                if key not in _NON_RULE_KEYS
            }
        )
        return _RulePack(path=path, scope=scope, rule_specs=rule_specs)

    def _read_scope(self, raw_header: object, path: Path) -> _PackScope:
        """Return the scope an applies_to header states; raise if it is malformed."""
        if not isinstance(raw_header, dict):
            raise ValueError(
                f"Rules file '{path}' has an invalid {_HEADER_KEY} header "
                f"{raw_header!r}; expected an object"
            )
        unknown_fields = sorted(
            str(key) for key in set(raw_header) - _HEADER_FIELD_NAMES
        )
        if unknown_fields:
            warnings.warn(
                f"The {_HEADER_KEY} header in '{path}' has unknown fields "
                f"{unknown_fields}, which are ignored; known fields: "
                f"{sorted(_HEADER_FIELD_NAMES)}",
                KlintWarning,
                stacklevel=2,
            )
        if "languages" not in raw_header:
            return _PackScope()
        raw_languages = raw_header["languages"]
        if (
            not isinstance(raw_languages, list)
            or not raw_languages
            or not all(isinstance(item, str) for item in raw_languages)
        ):
            raise ValueError(
                f"Rules file '{path}' has an invalid {_HEADER_KEY} header: "
                f"languages {raw_languages!r} must be a non-empty list of strings"
            )
        unknown_languages = self._find_unknown_languages(raw_languages)
        if unknown_languages:
            warnings.warn(
                f"The {_HEADER_KEY} header in '{path}' names unknown languages "
                f"{unknown_languages}, so the pack never loads for them; known "
                f"languages: {sorted(self._known_languages)}",
                KlintWarning,
                stacklevel=2,
            )
        return _PackScope(languages=tuple(raw_languages))

    def _load_pack_rules(self, pack: _RulePack) -> dict[str, AuditRule]:
        if pack.path not in self._path_to_rules:
            self._path_to_rules[pack.path] = self._build_rules(pack)
        return self._path_to_rules[pack.path]

    def _build_rules(self, pack: _RulePack) -> dict[str, AuditRule]:
        path = pack.path
        rules: dict[str, AuditRule] = {}
        for rule_id, spec in pack.rule_specs.items():
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
            if "tags" in spec:
                kwargs["tags"] = self._validate_string_list(
                    spec["tags"], "tags", rule_id
                )
            rule_languages = (
                self._validate_string_list(spec["languages"], "languages", rule_id)
                if "languages" in spec
                else []
            )
            self._validate_languages(rule_languages, rule_id, path)
            languages = pack.scope.narrow(rule_languages)
            if not self._keeps_languages_of_its_pack(
                rule_languages, languages, rule_id, path
            ):
                continue
            rules[rule_id] = AuditRule(**kwargs, languages=languages)
        return rules

    def _keeps_languages_of_its_pack(
        self,
        rule_languages: Sequence[str],
        narrowed_languages: Sequence[str],
        rule_id: str,
        path: Path,
    ) -> bool:
        """Warn about rule languages its pack leaves out; False if none are left."""
        outside = [
            language
            for language in rule_languages
            if language not in narrowed_languages
        ]
        if not outside:
            return True
        warnings.warn(
            f"Rule '{rule_id}' in '{path}' names languages {outside} that the "
            f"{_HEADER_KEY} header of its pack leaves out, so it never runs for them",
            KlintWarning,
            stacklevel=2,
        )
        return bool(narrowed_languages)

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
        unknown = self._find_unknown_languages(languages)
        if unknown:
            warnings.warn(
                f"Rule '{rule_id}' in '{path}' names unknown languages {unknown}, "
                "so it never runs for them; known languages: "
                f"{sorted(self._known_languages)}",
                KlintWarning,
                stacklevel=2,
            )

    def _find_unknown_languages(self, languages: Sequence[str]) -> list[str]:
        return [
            language
            for language in languages
            if language.lower() not in self._known_languages
        ]

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
