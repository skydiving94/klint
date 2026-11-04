"""The domain-neutral suite and the injector module that adds it to an audit."""

from injector import Binder, Module

from klint.catalog.domain_neutral.file_unit import AuditableFileUnit
from klint.core import UnitRegistry
from klint.core.interfaces import AuditKind, BaseSuite


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
