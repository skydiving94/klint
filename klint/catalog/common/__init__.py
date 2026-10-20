"""The suite of units that do not depend on what kind of content is audited."""

from injector import Binder, Module

from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_kind import AuditKind
from klint.core.registry import UnitRegistry


class DomainNeutralSuite(BaseSuite):
    """Unit types that fit any content; other suites build their audits on them."""

    def list_audit_kinds(self) -> list[AuditKind]:
        return []

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(AuditableFileUnit)


class DomainNeutralSuiteModule(Module):
    """Adds the domain-neutral suite to an audit."""

    def configure(self, binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[DomainNeutralSuite])
