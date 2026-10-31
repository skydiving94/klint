from abc import ABC, abstractmethod

from klint.core.models.rule_pack import RulePackSpec


class BaseRuleSource(ABC):
    """Where rule packs come from: a file, a document, a database or a call."""

    @abstractmethod
    def read_rule_packs(self) -> list[RulePackSpec]:
        """Return the rule packs this source holds, in merge order; may be none.

        Raises when the source cannot be read as rule packs.
        """
