"""A project's rule exclusions: one rule turned off for some of its paths."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuleExclusion:
    """One rule a project turns off for the paths its globs match.

    Each glob in paths is matched against a unit's path from base_directory
    down, such as "src/legacy/**"; a class or function is matched by its
    file's path. reason says why the rule does not apply there, such as a
    link to the comment that rebuts its finding.
    """

    base_directory: Path
    rule_id: str
    paths: tuple[str, ...]
    reason: str


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
