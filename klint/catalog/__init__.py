"""The built-in suites of units, extractors and kinds of audit."""

from injector import Binder, Module

from klint.catalog.code import CodeSuiteModule
from klint.catalog.common import DomainNeutralSuiteModule


class BuiltInSuitesModule(Module):
    """Adds every built-in suite to an audit."""

    def configure(self, binder: Binder) -> None:
        binder.install(DomainNeutralSuiteModule())
        binder.install(CodeSuiteModule())
