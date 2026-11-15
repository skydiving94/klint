"""The change-summary suite and the injector module that adds it to an audit."""

from injector import Binder, Module, ProviderOf, inject

from klint.catalog.change_summary.change_summary_extractor import (
    ChangeSummaryExtractor,
)
from klint.catalog.change_summary.documents import (
    ChangeSummarySourceFactory,
)
from klint.catalog.change_summary.renderers import (
    FileSummaryRenderer,
    HunkSummaryRenderer,
    PackageSummaryRenderer,
)
from klint.catalog.change_summary.summary_accuracy_scale import (
    SUMMARY_ACCURACY_SCALE,
)
from klint.catalog.change_summary.summary_check_tag import SummaryCheckTag
from klint.catalog.change_summary.units import (
    AuditableFileSummaryUnit,
    AuditableHunkSummaryUnit,
    AuditablePackageSummaryUnit,
)
from klint.catalog.domain_neutral import locate_built_in_catalog_file
from klint.core import UnitRegistry
from klint.core.interfaces import AuditKind, BaseSuite, UnitSource
from klint.core.models.audits import AuditInputKind, AuditOrder
from klint.infra.rule_loader import JsonFileRuleSource, RulePackLoader

# The kind of audit this suite offers: a change-summary document, verified.
CHANGE_SUMMARY_KIND_ID = "change_summary"
# The suite's checks, relative to klint/resources/catalog/.
SUMMARY_CHECKS_PACK = "change_summary/summary_checks.json"
# The most characters the judge reads about one summary. A hunk's code past
# the budget is cut, and small judges flag a summary of cut code whether or
# not it is true, so the budget leaves room for the hunks of a usual commit.
CHANGE_SUMMARY_CHARACTER_BUDGET = 4_000


class ChangeSummarySuite(BaseSuite):
    """Verifies an agent's summaries of a change, children first.

    A change-summary document is read from a JSON file or from JSON in
    memory. It holds the code of each hunk, or names a change that is read
    from the git repository of the current directory. Its summaries have no
    language, so every one is asked the suite's checks, and the custom rules
    of a request merge over them.
    """

    @inject
    def __init__(self, unit_registry_provider: ProviderOf[UnitRegistry]) -> None:
        # Asked for only when the kinds are listed: the rule loader checks
        # rules against the unit types the suites register.
        self._unit_registry_provider = unit_registry_provider

    def list_audit_kinds(self) -> list[AuditKind]:
        summary_checks = JsonFileRuleSource(
            locate_built_in_catalog_file(SUMMARY_CHECKS_PACK), is_required=True
        )
        return [
            AuditKind(
                kind_id=CHANGE_SUMMARY_KIND_ID,
                accepted_input_kinds=frozenset(
                    {AuditInputKind.DISK_PATH, AuditInputKind.IN_MEMORY_BYTES}
                ),
                unit_source=UnitSource(
                    ChangeSummarySourceFactory(), ChangeSummaryExtractor()
                ),
                rule_loader=RulePackLoader(
                    [summary_checks],
                    [summary_checks],
                    self._unit_registry_provider.get(),
                    known_languages=(),
                ),
                answer_scale=SUMMARY_ACCURACY_SCALE,
                unit_class_to_renderer={
                    AuditableHunkSummaryUnit: HunkSummaryRenderer(),
                    AuditableFileSummaryUnit: FileSummaryRenderer(),
                    AuditablePackageSummaryUnit: PackageSummaryRenderer(),
                },
                ranked_tags=(SummaryCheckTag.ACCURACY, SummaryCheckTag.COMPLETENESS),
                audit_order=AuditOrder.CHILDREN_FIRST,
                character_budget=CHANGE_SUMMARY_CHARACTER_BUDGET,
            )
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(AuditableHunkSummaryUnit)
        registry.register_unit(AuditableFileSummaryUnit)
        registry.register_unit(AuditablePackageSummaryUnit)


class ChangeSummarySuiteModule(Module):
    """Adds the change-summary suite to an audit."""

    def configure(self, binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[ChangeSummarySuite])
