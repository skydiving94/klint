"""The rule selection stage: the rules a run asks about its units."""

import warnings
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from klint.catalog.domain_neutral import does_name_match_glob, does_path_match_glob
from klint.core import KlintWarning
from klint.core.interfaces import AuditKind, BaseRuleSource
from klint.core.models.rules import (
    UNIT_SELECTOR_SEPARATOR,
    AppliedRuleExclusion,
    RuleExclusion,
    RuleExclusionSelector,
    RuleSet,
)
from klint.core.models.units import AuditableUnit, UnitTraits

_GLOB_CHARACTERS = frozenset("*?[")


class RuleSelection:
    """Loads the rules of a kind of audit by the traits of the units.

    rule_exclusions are the project's: each turns one rule off for the units
    its paths select.
    """

    def __init__(self, rule_exclusions: Sequence[RuleExclusion] = ()) -> None:
        self._rule_exclusions = tuple(rule_exclusions)

    async def select_rules(
        self,
        units: Sequence[AuditableUnit],
        audit_kind: AuditKind,
        custom_rule_source: BaseRuleSource | None = None,
        full_audit_path: Path | None = None,
    ) -> RuleSet:
        """Return the rule set that chooses the rules to ask about each unit.

        The rules are loaded once for each set of traits among the units.
        The rules of ``custom_rule_source``, when given, merge over the
        loaded ones. Raises when a rule source cannot be used. With no unit,
        the rules are still loaded once, so that such a source stops the
        audit whatever the input holds. An exclusion applies to a unit only
        where its rule would have been asked.

        ``full_audit_path``, when given, is the file or folder the units
        come from in full, as opposed to part of it, as a diff gives. Each
        path of an exclusion that lies inside it, whose rule this audit
        loads, and that kept its rule from no unit is then reported as a
        KlintWarning, once per exclusion.
        """
        traits_of_units = list(dict.fromkeys(unit.traits for unit in units)) or [
            UnitTraits()
        ]
        traits_to_rules = {
            traits: await audit_kind.rule_loader.load_rules(traits, custom_rule_source)
            for traits in traits_of_units
        }
        all_rules = RuleSet(traits_to_rules)
        loaded_rule_ids = {
            rule.rule_id for rules in traits_to_rules.values() for rule in rules
        }
        applied_exclusions: list[AppliedRuleExclusion] = []
        for exclusion in self._rule_exclusions:
            entry_to_unit_ids = {
                entry: _list_excluded_unit_ids(exclusion, entry, units, all_rules)
                for entry in exclusion.paths
            }
            unit_ids = tuple(
                dict.fromkeys(
                    unit_id
                    for entry_unit_ids in entry_to_unit_ids.values()
                    for unit_id in entry_unit_ids
                )
            )
            if unit_ids:
                applied_exclusions.append(AppliedRuleExclusion(exclusion, unit_ids))
            if full_audit_path is not None and exclusion.rule_id in loaded_rule_ids:
                _warn_of_unmatched_entries(
                    exclusion,
                    [
                        entry
                        for entry, entry_unit_ids in entry_to_unit_ids.items()
                        if not entry_unit_ids
                        and _is_inside(exclusion, entry, full_audit_path)
                    ],
                )
        return RuleSet(traits_to_rules, applied_exclusions)


def _list_excluded_unit_ids(
    exclusion: RuleExclusion,
    entry: str,
    units: Sequence[AuditableUnit],
    all_rules: RuleSet,
) -> list[str]:
    """Return the units the ``entry`` of its paths selects that would be asked it."""
    selector = RuleExclusionSelector.parse(entry)
    return [
        unit.unit_id
        for unit in units
        if _does_selector_match(exclusion.base_directory, selector, unit)
        and any(
            rule.rule_id == exclusion.rule_id
            for rule in all_rules.select_rules_for(unit)
        )
    ]


def _does_selector_match(
    base_directory: Path, selector: RuleExclusionSelector, unit: AuditableUnit
) -> bool:
    """Return True when ``selector`` covers ``unit``, by its path and its name."""
    location = unit.get_location()
    if location is None:
        return False
    try:
        path_in_project = Path(location.path).resolve().relative_to(base_directory)
    except ValueError:
        return False
    if not does_path_match_glob(path_in_project, selector.path_glob):
        return False
    if selector.unit_name_glob is None:
        return True
    name_glob = selector.unit_name_glob
    return any(
        does_name_match_glob(name, name_glob)
        for name in _list_enclosing_names(unit.unit_id, location.path)
    )


def _list_enclosing_names(unit_id: str, path: str) -> list[str]:
    """Return the qualified names of the unit and the units it is nested in.

    A unit's ID is its file's path, then "::" and its qualified name, which
    may end with ":" and its first line; the file unit has no name, so none
    is returned for it. "Cart.total" gives "Cart" and "Cart.total".
    """
    prefix = f"{path}{UNIT_SELECTOR_SEPARATOR}"
    if not unit_id.startswith(prefix):
        return []
    qualified_name = unit_id.removeprefix(prefix)
    name, _, first_line = qualified_name.rpartition(":")
    if name and first_line.isdigit():
        qualified_name = name
    parts = qualified_name.split(".")
    return [".".join(parts[: count + 1]) for count in range(len(parts))]


def _is_inside(exclusion: RuleExclusion, entry: str, full_audit_path: Path) -> bool:
    """Return True when the path the ``entry`` of its paths names is in the audit.

    The path a glob names is its folders up to the first one with a glob
    character in it.
    """
    literal_parts: list[str] = []
    for part in PurePosixPath(RuleExclusionSelector.parse(entry).path_glob).parts:
        if _GLOB_CHARACTERS & set(part):
            break
        literal_parts.append(part)
    named_path = exclusion.base_directory.joinpath(*literal_parts).resolve()
    return named_path.is_relative_to(full_audit_path.resolve())


def _warn_of_unmatched_entries(
    exclusion: RuleExclusion, unmatched_entries: Sequence[str]
) -> None:
    """Warn that the exclusion's ``unmatched_entries`` kept its rule from no unit."""
    if not unmatched_entries:
        return
    warnings.warn(
        f"The rule exclusion of '{exclusion.rule_id}' on "
        f"{', '.join(unmatched_entries)} matched no unit "
        "it would have been asked about: it may be stale, such as for a renamed "
        "class or function",
        KlintWarning,
        stacklevel=3,
    )
