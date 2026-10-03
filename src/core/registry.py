"""The unit types an audit knows about."""

from src.core.models.unit import AuditableUnit


class UnitRegistry:
    """Maps each unit_type tag to the unit class that declares it.

    Suites add their unit classes through ``register_unit``; rule loading
    checks a rule's target unit types against ``known_unit_types``.
    """

    def __init__(self) -> None:
        self._unit_classes: dict[str, type[AuditableUnit]] = {}

    def register_unit(self, unit_class: type[AuditableUnit]) -> None:
        """Add a unit class; registering the same class twice is harmless."""
        unit_type = unit_class.unit_type
        existing = self._unit_classes.get(unit_type)
        if existing is not None and existing is not unit_class:
            raise ValueError(
                f"Unit type '{unit_type}' is already registered by "
                f"{existing.__name__}; {unit_class.__name__} cannot reuse it"
            )
        self._unit_classes[unit_type] = unit_class

    def known_unit_types(self) -> list[str]:
        """Return every registered unit_type tag, sorted."""
        return sorted(self._unit_classes)
