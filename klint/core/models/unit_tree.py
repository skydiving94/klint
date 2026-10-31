"""How the units of an audit nest inside one another."""

from collections.abc import Iterable, Mapping

from klint.core.models.unit import AuditableUnit


def map_unit_id_to_parent_unit_id(units: Iterable[AuditableUnit]) -> dict[str, str]:
    """Return the ID of the unit each unit is nested directly inside.

    Every unit nested in ``units``, at any depth, has an entry, whether it
    is listed in ``units`` or not; a unit nested in none has no entry. A
    unit nested in two units keeps the first one found.
    """
    unit_id_to_parent_unit_id: dict[str, str] = {}

    def record_children(unit: AuditableUnit) -> None:
        for child in unit.children():
            if child.unit_id not in unit_id_to_parent_unit_id:
                unit_id_to_parent_unit_id[child.unit_id] = unit.unit_id
                record_children(child)

    for unit in units:
        record_children(unit)
    return unit_id_to_parent_unit_id


def list_ancestor_unit_ids(
    unit_id: str, unit_id_to_parent_unit_id: Mapping[str, str]
) -> list[str]:
    """Return the IDs of the units ``unit_id`` is nested in, nearest first."""
    ancestor_unit_ids: list[str] = []
    seen_unit_ids = {unit_id}
    parent_unit_id = unit_id_to_parent_unit_id.get(unit_id)
    # A unit whose ID repeats among its ancestors ends the walk.
    while parent_unit_id is not None and parent_unit_id not in seen_unit_ids:
        ancestor_unit_ids.append(parent_unit_id)
        seen_unit_ids.add(parent_unit_id)
        parent_unit_id = unit_id_to_parent_unit_id.get(parent_unit_id)
    return ancestor_unit_ids
