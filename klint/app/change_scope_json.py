"""What an audit limited to a change covered, as JSON output writes it."""

from dataclasses import asdict

from klint.catalog.domain_neutral.git import ChangeScope, DiffUnits
from klint.core.models.reports import JsonValue
from klint.core.models.units import AuditableUnit


def convert_change_scope_to_dict(
    scope: ChangeScope,
    diff_units: DiffUnits,
    extracted_unit_count: int,
    selected_unit_count: int,
) -> dict[str, JsonValue]:
    """Return the files and units an audit of a change covered."""
    return {
        "diff_units": diff_units.value,
        "files": list(scope.list_audited_paths()),
        "deleted_files": list(scope.deleted_paths),
        "unit_count": extracted_unit_count,
        "selected_unit_count": selected_unit_count,
        "selected_units": [
            _convert_unit_to_dict(unit) for unit in scope.unit_selector.selected_units
        ],
    }


def _convert_unit_to_dict(unit: AuditableUnit) -> dict[str, JsonValue]:
    """Return a selected unit as --json lists it: its ID, type, place and context."""
    location = unit.get_location()
    return {
        "unit_id": unit.unit_id,
        "unit_type": unit.unit_type,
        "location": None if location is None else asdict(location),
        "context": asdict(unit.get_context()),
    }
