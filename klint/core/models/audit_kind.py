"""One kind of audit a suite offers."""

from dataclasses import dataclass

from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.target_extractor import BaseTargetExtractor
from klint.core.models.ignored_names import IgnoredNames
from klint.core.models.scale import AnswerScale


@dataclass(frozen=True)
class AuditKind:
    """What one kind of audit goes through, and how it is judged.

    kind_id names the kind in a request. extractor turns the scanned target
    into units, and rule_loader loads the rules asked about them. The judge
    answers each rule on answer_scale. A scan for this kind leaves out
    ignored_names.
    """

    kind_id: str
    extractor: BaseTargetExtractor
    rule_loader: BaseRuleLoader
    answer_scale: AnswerScale
    ignored_names: IgnoredNames
