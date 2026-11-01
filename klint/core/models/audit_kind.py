"""One kind of audit a suite offers."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.renderer import BaseUnitRenderer
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.scan_progress_listener import BaseScanProgressListener
from klint.core.interfaces.source import BaseAuditSourceFactory
from klint.core.interfaces.unit_source import BaseUnitSource
from klint.core.models.acquired_units import AcquiredUnits
from klint.core.models.audit_input import AuditInput, AuditInputKind
from klint.core.models.audit_order import AuditOrder
from klint.core.models.render_input import DEFAULT_CHARACTER_BUDGET
from klint.core.models.scale import AnswerScale
from klint.core.models.unit import AuditableUnit

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
    rule on answer_scale. unit_class_to_renderer gives, for each class of
    unit, the renderer that writes what the judge reads about such units, in
    at most character_budget characters. ranked_tags are the rule tags whose
    findings a report lists first, most important first. audit_order is the
    order in which the units are judged.
    """

    kind_id: str
    accepted_input_kinds: frozenset[AuditInputKind]
    unit_source: BaseUnitSource
    rule_loader: BaseRuleLoader
    answer_scale: AnswerScale
    unit_class_to_renderer: Mapping[type[AuditableUnit], BaseUnitRenderer]
    ranked_tags: tuple[str, ...] = ()
    audit_order: AuditOrder = AuditOrder.ALL_AT_ONCE
    character_budget: int = DEFAULT_CHARACTER_BUDGET

    def __post_init__(self) -> None:
        if self.character_budget < 1:
            raise ValueError(
                f"Audit kind '{self.kind_id}' needs a character budget of at "
                f"least 1, not {self.character_budget}"
            )

    def find_renderer(self, unit: AuditableUnit) -> BaseUnitRenderer:
        """Return the renderer for ``unit``.

        That is the renderer given for its class, else for its nearest base
        class that has one. Raises ValueError when there is none.
        """
        for unit_class in type(unit).__mro__:
            for rendered_class, renderer in self.unit_class_to_renderer.items():
                if rendered_class is unit_class:
                    return renderer
        raise ValueError(
            f"Audit kind '{self.kind_id}' has no renderer for "
            f"{type(unit).__name__} units"
        )
