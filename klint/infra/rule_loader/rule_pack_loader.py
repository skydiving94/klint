import asyncio
import warnings
from collections.abc import Collection, Iterator, Sequence

from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.klint_warning import KlintWarning
from klint.core.models.rule import AuditRule
from klint.core.models.rule_pack import RulePackSpec, RuleProblemSeverity, RuleSpec
from klint.core.models.unit_traits import UnitTraits
from klint.core.registry import UnitRegistry
from klint.infra.rule_loader.rule_pack_reader import HEADER_KEY


class RulePackLoader(BaseRuleLoader):
    """Loads rules from the packs of rule sources, choosing packs by unit traits.

    A unit of an identified language is asked every pack whose applies_to
    header matches its traits; a pack without a header matches every such
    unit. A unit whose language is not identified is asked the packs of the
    fallback sources instead. A rule inherits its pack's languages and may
    narrow them. The rules of project_rule_sources, a project's own, merge
    over the chosen packs for every unit, and custom rules merge over them
    all. Each source is read when the first load needs its packs' headers,
    but the problems in a pack's rules are reported only once it is chosen.

    A source that cannot be read as rules stops the load with an error, as
    does a rule with a field of the wrong kind or an unknown unit type. Any
    other problem in one rule is reported as a KlintWarning and the load goes
    on. known_languages are the languages a unit can be identified as.
    """

    def __init__(
        self,
        rule_sources: Sequence[BaseRuleSource],
        fallback_rule_sources: Sequence[BaseRuleSource],
        unit_registry: UnitRegistry,
        known_languages: Collection[str],
        project_rule_sources: Sequence[BaseRuleSource] = (),
    ) -> None:
        self._rule_sources = list(rule_sources)
        self._fallback_rule_sources = list(fallback_rule_sources)
        self._project_rule_sources = list(project_rule_sources)
        self._unit_registry = unit_registry
        self._known_languages = {language.lower() for language in known_languages}
        # Each source is read and each pack checked once, however many loads
        # use them.
        self._source_to_packs: dict[BaseRuleSource, list[RulePackSpec]] = {}
        self._pack_to_rules: dict[RulePackSpec, dict[str, AuditRule]] = {}
        self._lock = asyncio.Lock()

    async def load_rules(
        self, traits: UnitTraits, custom_rule_source: BaseRuleSource | None = None
    ) -> list[AuditRule]:
        async with self._lock:
            return await asyncio.to_thread(
                self._load_rules_sync, traits, custom_rule_source
            )

    def _load_rules_sync(
        self, traits: UnitTraits, custom_rule_source: BaseRuleSource | None
    ) -> list[AuditRule]:
        """Merge the chosen packs, the project's, then the custom rules, by rule ID."""
        rules: dict[str, AuditRule] = {}
        for pack in self._choose_packs(traits):
            rules.update(self._load_pack_rules(pack))
        sources_merged_last = list(self._project_rule_sources)
        if custom_rule_source is not None:
            sources_merged_last.append(custom_rule_source)
        for source in sources_merged_last:
            for pack in self._read_packs(source):
                rules.update(self._load_pack_rules(pack))
        return list(rules.values())

    def _choose_packs(self, traits: UnitTraits) -> Iterator[RulePackSpec]:
        language = traits.language
        if language is None:
            for source in self._fallback_rule_sources:
                yield from self._read_packs(source)
            return
        for source in self._rule_sources:
            for pack in self._read_packs(source):
                if pack.scope.matches(language):
                    yield pack

    def _read_packs(self, source: BaseRuleSource) -> list[RulePackSpec]:
        """Return the packs of ``source``, read the first time they are needed."""
        if source not in self._source_to_packs:
            packs = source.read_rule_packs()
            for pack in packs:
                self._warn_about_unknown_header_languages(pack)
            self._source_to_packs[source] = packs
        return self._source_to_packs[source]

    def _warn_about_unknown_header_languages(self, pack: RulePackSpec) -> None:
        unknown_languages = self._find_unknown_languages(pack.scope.languages or ())
        if unknown_languages:
            warnings.warn(
                f"The {HEADER_KEY} header in '{pack.origin}' names unknown languages "
                f"{unknown_languages}, so the pack never loads for them; known "
                f"languages: {sorted(self._known_languages)}",
                KlintWarning,
                stacklevel=2,
            )

    def _load_pack_rules(self, pack: RulePackSpec) -> dict[str, AuditRule]:
        if pack not in self._pack_to_rules:
            self._report_rule_problems(pack)
            self._pack_to_rules[pack] = {
                rule.rule_id: rule
                for rule in (self._build_rule(spec, pack) for spec in pack.rules)
                if rule is not None
            }
        return self._pack_to_rules[pack]

    def _report_rule_problems(self, pack: RulePackSpec) -> None:
        """Warn about each problem in the pack's rules; raise at the first error."""
        for problem in pack.rule_problems:
            if problem.severity is RuleProblemSeverity.ERROR:
                raise ValueError(problem.message)
            warnings.warn(problem.message, KlintWarning, stacklevel=2)

    def _build_rule(self, spec: RuleSpec, pack: RulePackSpec) -> AuditRule | None:
        """Return the rule ``spec`` writes, in its pack; None when it never runs."""
        self._check_unit_types(spec, pack.origin)
        self._warn_about_unknown_rule_languages(spec, pack.origin)
        languages = pack.scope.narrow(spec.languages)
        if not self._keeps_languages_of_its_pack(spec, languages, pack.origin):
            return None
        return AuditRule(
            rule_id=spec.rule_id,
            question_type=spec.question_type,
            question=spec.question,
            target_unit_types=list(spec.target_unit_types),
            languages=languages,
            tags=list(spec.tags),
            unit_tags=list(spec.unit_tags),
        )

    def _keeps_languages_of_its_pack(
        self, spec: RuleSpec, narrowed_languages: Sequence[str], origin: str
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
            f"Rule '{spec.rule_id}' in '{origin}' names languages {outside} that the "
            f"{HEADER_KEY} header of its pack leaves out, so it never runs for them",
            KlintWarning,
            stacklevel=2,
        )
        return bool(narrowed_languages)

    def _warn_about_unknown_rule_languages(self, spec: RuleSpec, origin: str) -> None:
        """Warn about languages no unit can be identified as."""
        unknown = self._find_unknown_languages(spec.languages)
        if unknown:
            warnings.warn(
                f"Rule '{spec.rule_id}' in '{origin}' names unknown languages "
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

    def _check_unit_types(self, spec: RuleSpec, origin: str) -> None:
        """Raise when the rule names a unit type no suite registers."""
        known = set(self._unit_registry.known_unit_types())
        unknown = [
            unit_type for unit_type in spec.target_unit_types if unit_type not in known
        ]
        if unknown:
            raise ValueError(
                f"Rule '{spec.rule_id}' has unknown target_unit_types {unknown} "
                f"in '{origin}'; known: {sorted(known)}"
            )
