"""A rule source that reads one JSON rules file."""

from dataclasses import dataclass
from pathlib import Path

from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.models.rule_pack import RulePackSpec
from klint.infra.rule_loader.rule_pack_reader import read_rule_pack


@dataclass(frozen=True)
class JsonFileRuleSource(BaseRuleSource):
    """Reads the rule pack written in the JSON file at ``path``.

    A file that does not exist holds no pack, unless is_required: then it
    raises FileNotFoundError. A file that cannot be read as rules raises
    ValueError naming it.
    """

    path: Path
    is_required: bool = False

    def read_rule_packs(self) -> list[RulePackSpec]:
        if not self.path.is_file():
            if self.is_required:
                raise FileNotFoundError(f"Rules file does not exist: {self.path}")
            return []
        return [read_rule_pack(self.path)]
