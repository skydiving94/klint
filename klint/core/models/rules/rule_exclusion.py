"""A project's rule exclusions: one rule turned off for some of its paths."""

from dataclasses import dataclass
from pathlib import Path

# What separates a unit selector's file glob from its qualified-name glob.
UNIT_SELECTOR_SEPARATOR = "::"


@dataclass(frozen=True)
class RuleExclusionSelector:
    """One entry of an exclusion's paths: the units it turns its rule off for.

    path_glob is matched against a unit's file or folder path. unit_name_glob,
    when given, is matched against the qualified name of a class or function
    in that file, such as "Cart.total"; a unit is covered when its name, or
    the name of a unit it is nested in, matches, and the file unit is not.
    Without one, every unit whose path matches is covered.
    """

    path_glob: str
    unit_name_glob: str | None = None

    @classmethod
    def parse(cls, entry: str) -> "RuleExclusionSelector":
        """Return the selector an entry of paths writes, such as "a.py::Cart"."""
        path_glob, separator, unit_name_glob = entry.partition(UNIT_SELECTOR_SEPARATOR)
        return cls(path_glob, unit_name_glob if separator else None)

    def is_complete(self) -> bool:
        """Return True when the selector names a path, and a unit after "::"."""
        return bool(self.path_glob) and self.unit_name_glob != ""


@dataclass(frozen=True)
class RuleExclusion:
    """One rule a project turns off for the units its paths select.

    Each entry of paths is a glob matched against a unit's path from
    base_directory down, such as "src/legacy/**", which covers a file and
    every class and function in it; or a unit selector, such as
    "cart.py::Cart", which covers that class and the units nested in it.
    reason says why the rule does not apply there, such as a link to the
    comment that rebuts its finding.
    """

    base_directory: Path
    rule_id: str
    paths: tuple[str, ...]
    reason: str

    def list_selectors(self) -> tuple[RuleExclusionSelector, ...]:
        """Return the selectors its paths write, in order."""
        return tuple(RuleExclusionSelector.parse(entry) for entry in self.paths)

    def does_select_units(self) -> bool:
        """Return True when one of its paths is a unit selector."""
        return any(
            selector.unit_name_glob is not None for selector in self.list_selectors()
        )


@dataclass(frozen=True)
class AppliedRuleExclusion:
    """A rule exclusion, and the units it kept its rule from being asked about."""

    exclusion: RuleExclusion
    unit_ids: tuple[str, ...]

    def convert_to_dict(self) -> dict[str, object]:
        """Return the exclusion as JSON output gives it."""
        return {
            "rule_id": self.exclusion.rule_id,
            "paths": list(self.exclusion.paths),
            "reason": self.exclusion.reason,
            "unit_ids": list(self.unit_ids),
        }
