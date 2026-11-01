"""Builds the tree of summary units of a change-summary document, in one pass."""

from klint.catalog.change_summary.document import FileSummary, PackageSummary
from klint.catalog.change_summary.document_reader import (
    ROOT_PACKAGE_PATH,
    read_change_summary_document,
)
from klint.catalog.change_summary.units.file_summary import AuditableFileSummaryUnit
from klint.catalog.change_summary.units.hunk_summary_unit import (
    AuditableHunkSummaryUnit,
)
from klint.catalog.change_summary.units.package_summary import (
    AuditablePackageSummaryUnit,
)
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.models.json_value import JsonValue
from klint.core.models.unit import AuditableUnit


class ChangeSummaryExtractor(BaseUnitExtractor[JsonValue]):
    """Reads a change-summary document into a unit per summary, at every level.

    A hunk's unit ID is its hunk_id and a file's is its path. A package's is
    its path with a slash after it, "./" for the root package, so that a
    package never shares an ID with a file.
    """

    async def extract(self, audit_input: JsonValue) -> list[AuditableUnit]:
        """Return the root package's unit, then every unit nested in it.

        Each unit comes before the units nested inside it, in document
        order: a package's packages, then its files. Raises ValueError when
        the document is not a change-summary document, its packages are
        nested too deeply to read, or two of its summaries would have the
        same unit ID.
        """
        try:
            document = read_change_summary_document(audit_input)
            units = _list_unit_and_nested(_build_package_unit(document.root_package))
        except RecursionError as error:
            raise ValueError(
                "Change-summary document: #/root_package holds packages nested "
                "too deeply to read"
            ) from error
        _check_unit_ids_differ(units)
        return units


def _build_package_unit(package: PackageSummary) -> AuditablePackageSummaryUnit:
    is_root_package = package.path == ROOT_PACKAGE_PATH
    return AuditablePackageSummaryUnit(
        unit_id=f"{package.path}/",
        path=package.path,
        summary=package.summary,
        pointer=package.pointer,
        is_root_package=is_root_package,
        packages=tuple(_build_package_unit(nested) for nested in package.packages),
        files=tuple(_build_file_unit(file) for file in package.files),
    )


def _build_file_unit(file: FileSummary) -> AuditableFileSummaryUnit:
    return AuditableFileSummaryUnit(
        unit_id=file.path,
        path=file.path,
        summary=file.summary,
        pointer=file.pointer,
        change_kind=file.change_kind,
        old_path=file.old_path,
        hunks=tuple(
            AuditableHunkSummaryUnit(
                unit_id=hunk.hunk_id,
                hunk=hunk,
                file_path=file.path,
                file_old_path=file.old_path,
                file_change_kind=file.change_kind,
            )
            for hunk in file.hunks
        ),
    )


def _list_unit_and_nested(unit: AuditableUnit) -> list[AuditableUnit]:
    """Return ``unit``, then each unit nested in it, each before its own."""
    units = [unit]
    for child in unit.children():
        units.extend(_list_unit_and_nested(child))
    return units


def _check_unit_ids_differ(units: list[AuditableUnit]) -> None:
    """Raise ValueError naming the first unit ID two units share."""
    unit_id_to_location: dict[str, str] = {}
    for unit in units:
        location = unit.get_location()
        source = "" if location is None else location.source
        earlier_source = unit_id_to_location.setdefault(unit.unit_id, source)
        if earlier_source != source:
            raise ValueError(
                f"Change-summary document: {source} has the ID '{unit.unit_id}', "
                f"as {earlier_source} does; each hunk ID, file path and package "
                "path appears once"
            )
