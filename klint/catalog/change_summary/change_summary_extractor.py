"""Builds the tree of summary units of a change-summary document, in one pass."""

from klint.catalog.change_summary.documents import (
    ROOT_PACKAGE_PATH,
    ChangeSummaryDocument,
    ChangeSummaryInput,
    FileSummary,
    PackageSummary,
    read_change_summary_document,
    read_summaries_of_git_change,
)
from klint.catalog.change_summary.units import (
    AuditableFileSummaryUnit,
    AuditableHunkSummaryUnit,
    AuditablePackageSummaryUnit,
)
from klint.core.interfaces import BaseUnitExtractor
from klint.core.models.units import AuditableUnit


class ChangeSummaryExtractor(BaseUnitExtractor[ChangeSummaryInput]):
    """Reads a change-summary document into a unit per summary, at every level.

    A document either holds each hunk's code, or holds summaries only and
    comes with its change, read from git. In the second case, every hunk
    and file of the change, and the root package, has a unit, whether the
    document summarizes it or not.

    A hunk's unit ID is its hunk_id, or "<file path>#<number>" for a hunk
    read from git, numbered from 1 in the file. A file's is its path. A
    package's is its path with a slash after it, "./" for the root package,
    so that a package never shares an ID with a file.
    """

    async def extract(self, audit_input: ChangeSummaryInput) -> list[AuditableUnit]:
        """Return the root package's unit, then every unit nested in it.

        Each unit comes before the units nested inside it, in document
        order: a package's packages, then its files. Raises ValueError when
        the document is not a change-summary document, its packages are
        nested too deeply to read, a summary is about something the change
        does not hold, or two of its summaries would have the same unit ID.
        """
        try:
            document = _read_document(audit_input)
            units = _list_unit_and_nested(_build_package_unit(document.root_package))
        except RecursionError as error:
            raise ValueError(
                "Change-summary document: #/root_package holds packages nested "
                "too deeply to read"
            ) from error
        _check_unit_ids_differ(units)
        return units


def _read_document(audit_input: ChangeSummaryInput) -> ChangeSummaryDocument:
    if audit_input.git_change is None:
        return read_change_summary_document(audit_input.document)
    return read_summaries_of_git_change(audit_input.document, audit_input.git_change)


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
    for child in unit.list_children():
        units.extend(_list_unit_and_nested(child))
    return units


def _check_unit_ids_differ(units: list[AuditableUnit]) -> None:
    """Raise ValueError naming the first unit ID two units share."""
    unit_id_to_path: dict[str, str] = {}
    for unit in units:
        location = unit.get_location()
        path = "" if location is None else location.path
        earlier_path = unit_id_to_path.setdefault(unit.unit_id, path)
        if earlier_path != path:
            raise ValueError(
                f"Change-summary document: {path} has the ID '{unit.unit_id}', "
                f"as {earlier_path} does; each hunk ID, file path and package "
                "path appears once"
            )
