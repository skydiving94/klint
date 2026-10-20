"""The suite for code: the contents of files and the structure of projects."""

from injector import Binder, Module, ProviderOf, inject

from klint.catalog.code import python
from klint.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from klint.catalog.code.common.extractors.file_contents import FileContentsExtractor
from klint.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.common.extractors.project_structure import (
    ProjectStructureExtractor,
)
from klint.catalog.code.common.ignored_names import CODE_IGNORED_NAMES
from klint.catalog.code.common.practice_scale import PRACTICE_SCALE
from klint.catalog.code.common.units.directory import AuditableDirectoryUnit
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from klint.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from klint.catalog.common.units.file import AuditableFileUnit
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_kind import AuditKind
from klint.core.registry import UnitRegistry

# The kinds of audit this suite offers: each file's contents, and the
# structure of a project's directories.
FILE_CONTENTS_KIND_ID = "file_contents"
PROJECT_STRUCTURE_KIND_ID = "project_structure"


class CodeSuite(BaseSuite):
    """Audits code files and project structure, in any language."""

    @inject
    def __init__(
        self,
        file_contents_extractor: FileContentsExtractor,
        project_structure_extractor: ProjectStructureExtractor,
        rule_loader_provider: ProviderOf[BaseRuleLoader],
    ) -> None:
        self._file_contents_extractor = file_contents_extractor
        self._project_structure_extractor = project_structure_extractor
        # Asked for only when the kinds are listed: the rule loader checks
        # rules against the unit types the suites register.
        self._rule_loader_provider = rule_loader_provider

    def list_audit_kinds(self) -> list[AuditKind]:
        rule_loader = self._rule_loader_provider.get()
        return [
            AuditKind(
                kind_id=FILE_CONTENTS_KIND_ID,
                extractor=self._file_contents_extractor,
                rule_loader=rule_loader,
                answer_scale=PRACTICE_SCALE,
                ignored_names=CODE_IGNORED_NAMES,
            ),
            AuditKind(
                kind_id=PROJECT_STRUCTURE_KIND_ID,
                extractor=self._project_structure_extractor,
                rule_loader=rule_loader,
                answer_scale=PRACTICE_SCALE,
                ignored_names=CODE_IGNORED_NAMES,
            ),
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(AuditableFileUnit)
        registry.register_unit(AuditableFileMetadataUnit)
        registry.register_unit(AuditableDirectoryUnit)


class CodeSuiteModule(Module):
    """Adds the code suite to an audit, with what handles each language."""

    def configure(self, binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[CodeSuite])
        # What handles each language, looked up by the traits of each file. A
        # language not listed is handled in a language-neutral way.
        binder.multibind(dict[str, BaseUnitExtractor], to={})
        binder.multibind(
            dict[str, BaseFileMetadataExtractor],
            to={python.SUITE_LANGUAGE: PythonFileMetadataExtractor},
        )
        binder.multibind(
            dict[str, BaseDirectoryUnitFactory],
            to={python.SUITE_LANGUAGE: PythonPackageUnitFactory},
        )
