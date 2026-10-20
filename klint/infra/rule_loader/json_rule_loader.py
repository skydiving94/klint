import asyncio
import warnings
from collections.abc import Collection, Iterator, Sequence
from pathlib import Path

from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.klint_warning import KlintWarning
from klint.core.models.file_traits import FileTraits
from klint.core.models.rule import AuditRule
from klint.core.registry import UnitRegistry
from klint.infra.rule_loader.rule_pack_reader import (
    HEADER_KEY,
    RulePackSpec,
    RuleProblemSeverity,
    RuleSpec,
    read_rule_pack,
)


class JsonRuleLoader(BaseRuleLoader):
    """Loads rules from JSON rule packs, choosing the packs by the traits of files.

    A file of an identified language is asked every pack whose applies_to
    header matches its traits; a pack without a header matches every such
    file. A file whose language is not identified is asked the fallback
    packs instead. A rule inherits its pack's languages and may narrow them.
    The rules of project_rule_packs, a project's own, merge over the chosen
    packs for every file, and custom rules merge over them all.
    Every pack file is read when the first load needs its header, but the
    problems in its rules are reported only once the pack is chosen.

    A file that cannot be read as rules stops the load with an error, as does
    a rule with a field of the wrong kind or an unknown unit type. Any other
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
        project_rule_packs: Sequence[Path] = (),
    ) -> None:
        self._rule_packs = list(rule_packs)
        self._fallback_rule_packs = list(fallback_rule_packs)
        self._project_rule_packs = list(project_rule_packs)
        self._unit_registry = unit_registry
        self._known_languages = {language.lower() for language in known_languages}
        # Each file is read and checked once, however many loads use it.
        self._path_to_pack: dict[Path, RulePackSpec | None] = {}
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
        """Merge the chosen packs, the project's, then the custom rules, by rule ID."""
        rules: dict[str, AuditRule] = {}
        for pack in self._choose_packs(traits):
            rules.update(self._load_pack_rules(pack))
        for path in self._project_rule_packs:
            project_pack = self._read_pack(path)
            if project_pack is not None:
                rules.update(self._load_pack_rules(project_pack))
        if custom_path is not None:
            rules.update(self._load_pack_rules(self._read_custom_pack(custom_path)))
        return list(rules.values())

    def _choose_packs(self, traits: FileTraits) -> Iterator[RulePackSpec]:
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

    def _read_pack(self, path: Path) -> RulePackSpec | None:
        """Return the pack at ``path``; None when there is no such file."""
        if path not in self._path_to_pack:
            pack = read_rule_pack(path) if path.exists() else None
            if pack is not None:
                self._warn_about_unknown_header_languages(pack)
            self._path_to_pack[path] = pack
        return self._path_to_pack[path]

    def _read_custom_pack(self, path: Path) -> RulePackSpec:
        if not path.is_file():
            raise FileNotFoundError(f"Custom rules file does not exist: {path}")
        pack = self._read_pack(path)
        assert pack is not None
        return pack

    def _warn_about_unknown_header_languages(self, pack: RulePackSpec) -> None:
        unknown_languages = self._find_unknown_languages(pack.scope.languages or ())
        if unknown_languages:
            warnings.warn(
                f"The {HEADER_KEY} header in '{pack.path}' names unknown languages "
                f"{unknown_languages}, so the pack never loads for them; known "
                f"languages: {sorted(self._known_languages)}",
                KlintWarning,
                stacklevel=2,
            )

    def _load_pack_rules(self, pack: RulePackSpec) -> dict[str, AuditRule]:
        if pack.path not in self._path_to_rules:
            self._report_rule_problems(pack)
            self._path_to_rules[pack.path] = {
                rule.rule_id: rule
                for rule in (self._build_rule(spec, pack) for spec in pack.rules)
                if rule is not None
            }
        return self._path_to_rules[pack.path]

    def _report_rule_problems(self, pack: RulePackSpec) -> None:
        """Warn about each problem in the pack's rules; raise at the first error."""
        for problem in pack.rule_problems:
            if problem.severity is RuleProblemSeverity.ERROR:
                raise ValueError(problem.message)
            warnings.warn(problem.message, KlintWarning, stacklevel=2)

    def _build_rule(self, spec: RuleSpec, pack: RulePackSpec) -> AuditRule | None:
        """Return the rule ``spec`` writes, in its pack; None when it never runs."""
        self._check_unit_types(spec, pack.path)
        self._warn_about_unknown_rule_languages(spec, pack.path)
        languages = pack.scope.narrow(spec.languages)
        if not self._keeps_languages_of_its_pack(spec, languages, pack.path):
            return None
        return AuditRule(
            rule_id=spec.rule_id,
            question_type=spec.question_type,
            instructions=spec.instructions,
            target_unit_types=list(spec.target_unit_types),
            languages=languages,
            tags=list(spec.tags),
        )

    def _keeps_languages_of_its_pack(
        self, spec: RuleSpec, narrowed_languages: Sequence[str], path: Path
    ) -> bool:
        """Warn about rule languages its pack leaves out; False if none are left."""
        outside = [
            language
            for language in spec.languages
            if language not in narrowed_languages
        ]
        if not outside:
            return True
        warnings.warn(
            f"Rule '{spec.rule_id}' in '{path}' names languages {outside} that the "
            f"{HEADER_KEY} header of its pack leaves out, so it never runs for them",
            KlintWarning,
            stacklevel=2,
        )
        return bool(narrowed_languages)

    def _warn_about_unknown_rule_languages(self, spec: RuleSpec, path: Path) -> None:
        """Warn about languages no file can be identified as."""
        unknown = self._find_unknown_languages(spec.languages)
        if unknown:
            warnings.warn(
                f"Rule '{spec.rule_id}' in '{path}' names unknown languages "
                f"{unknown}, so it never runs for them; known languages: "
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

    def _check_unit_types(self, spec: RuleSpec, path: Path) -> None:
        """Raise when the rule names a unit type no suite registers."""
        known = set(self._unit_registry.known_unit_types())
        unknown = [
            unit_type for unit_type in spec.target_unit_types if unit_type not in known
        ]
        if unknown:
            raise ValueError(
                f"Rule '{spec.rule_id}' has unknown target_unit_types {unknown} "
                f"in '{path}'; known: {sorted(known)}"
            )
