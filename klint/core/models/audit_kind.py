"""One kind of audit a suite offers."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.interfaces.source import BaseAuditSourceFactory
from klint.core.interfaces.unit_source import BaseUnitSource
from klint.core.models.acquired_units import AcquiredUnits
from klint.core.models.audit_input import AuditInput, AuditInputKind
from klint.core.models.scale import AnswerScale

# What the source reads an audit input into, and the extractor takes.
InputT = TypeVar("InputT")


class UnitSource(BaseUnitSource, Generic[InputT]):
    """Reads an audit input through a source, then extracts its units.

    The type parameter checks, where a unit source is built, that the
    extractor takes what the factory's sources read.
    """

    def __init__(
        self,
        source_factory: BaseAuditSourceFactory[InputT],
        extractor: BaseUnitExtractor[InputT],
    ) -> None:
        self._source_factory = source_factory
        self._extractor = extractor

    async def read_units(
        self,
        audit_input: AuditInput,
        scan_progress_listener: BaseScanProgressListener | None = None,
    ) -> AcquiredUnits:
        source = self._source_factory.create_source(audit_input, scan_progress_listener)
        units = await self._extractor.extract(await source.read_input())
        return AcquiredUnits(
            units=units, scanned_file_count=source.count_scanned_files()
        )


@dataclass(frozen=True)
class AuditKind:
    """What one kind of audit goes through, and how it is judged.

    kind_id names the kind in a request. accepted_input_kinds are the forms
    of input the kind takes. unit_source reads an input and gives its units,
    and rule_loader loads the rules asked about them. The judge answers each
    rule on answer_scale. ranked_tags are the rule tags whose findings a
    report lists first, most important first.
    """

    kind_id: str
    accepted_input_kinds: frozenset[AuditInputKind]
    unit_source: BaseUnitSource
    rule_loader: BaseRuleLoader
    answer_scale: AnswerScale
    ranked_tags: tuple[str, ...] = ()
