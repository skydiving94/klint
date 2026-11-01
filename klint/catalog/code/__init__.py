"""The suite for code: the contents of files and the structure of projects."""

from injector import Binder, Module, ProviderOf, inject, provider

from klint.catalog.code import python
from klint.catalog.code.language_neutral.extraction.directory_factory import (
    BaseDirectoryUnitFactory,
)
from klint.catalog.code.language_neutral.extraction.file_contents import (
    FileContentsExtractor,
)
from klint.catalog.code.language_neutral.extraction.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.language_neutral.extraction.language_neutral_directory_factory import (  # noqa: E501
    LanguageNeutralDirectoryUnitFactory,
)
from klint.catalog.code.language_neutral.extraction.language_neutral_file_metadata import (  # noqa: E501
    LanguageNeutralFileMetadataExtractor,
)
from klint.catalog.code.language_neutral.extraction.project import (
    RecursiveProjectExtractor,
)
from klint.catalog.code.language_neutral.extraction.project_structure import (
    ProjectStructureExtractor,
)
from klint.catalog.code.language_neutral.ignored_names import CODE_IGNORED_NAMES
from klint.catalog.code.language_neutral.practice_scale import PRACTICE_SCALE
from klint.catalog.code.language_neutral.renderers.directory import DirectoryRenderer
from klint.catalog.code.language_neutral.renderers.file_metadata import (
    FileMetadataRenderer,
)
from klint.catalog.code.language_neutral.units.directory import AuditableDirectoryUnit
from klint.catalog.code.language_neutral.units.file_metadata import (
    AuditableFileMetadataUnit,
)
from klint.catalog.code.python.extraction.file_metadata import (
    PythonFileMetadataExtractor,
)
from klint.catalog.code.python.extraction.package_factory import (
    PythonPackageUnitFactory,
)
from klint.catalog.code.python.renderers.package import PythonPackageRenderer
from klint.catalog.code.python.units.package import AuditablePythonPackageUnit
from klint.catalog.domain_neutral.extraction.dispatched_file import DispatchedFile
from klint.catalog.domain_neutral.extraction.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from klint.catalog.domain_neutral.extraction.whole_file import WholeFileExtractor
from klint.catalog.domain_neutral.renderers.whole_file import WholeFileRenderer
from klint.catalog.domain_neutral.sources.directory_tree_source import (
    DirectoryTreeSourceFactory,
)
from klint.catalog.domain_neutral.units.file import AuditableFileUnit
from klint.core.interfaces.extractor import BaseUnitExtractor
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.suite import BaseSuite
from klint.core.models.audit_input import AuditInputKind
from klint.core.models.audit_kind import AuditKind, UnitSource
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
        file_traits_identifier: BaseFileTraitsIdentifier,
        file_contents_extractor: FileContentsExtractor,
        project_structure_extractor: ProjectStructureExtractor,
        rule_loader_provider: ProviderOf[BaseRuleLoader],
    ) -> None:
        # Both kinds read a file or directory on disk.
        self._directory_tree_source_factory = DirectoryTreeSourceFactory(
            file_traits_identifier, CODE_IGNORED_NAMES
        )
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
                accepted_input_kinds=frozenset({AuditInputKind.DISK_PATH}),
                unit_source=UnitSource(
                    self._directory_tree_source_factory, self._file_contents_extractor
                ),
                rule_loader=rule_loader,
                answer_scale=PRACTICE_SCALE,
                unit_class_to_renderer={AuditableFileUnit: WholeFileRenderer()},
            ),
            AuditKind(
                kind_id=PROJECT_STRUCTURE_KIND_ID,
                accepted_input_kinds=frozenset({AuditInputKind.DISK_PATH}),
                unit_source=UnitSource(
                    self._directory_tree_source_factory,
                    self._project_structure_extractor,
                ),
                rule_loader=rule_loader,
                answer_scale=PRACTICE_SCALE,
                unit_class_to_renderer={
                    AuditableFileMetadataUnit: FileMetadataRenderer(),
                    AuditableDirectoryUnit: DirectoryRenderer(),
                    AuditablePythonPackageUnit: PythonPackageRenderer(),
                },
            ),
        ]

    def register_unit_types(self, registry: UnitRegistry) -> None:
        registry.register_unit(AuditableFileUnit)
        registry.register_unit(AuditableFileMetadataUnit)
        registry.register_unit(AuditableDirectoryUnit)


class CodeSuiteModule(Module):
    """Adds the code suite to an audit, with what handles each language.

    Each kind of audit picks what handles a file or directory by its traits,
    from the bindings for each language here. A language with nothing bound
    is handled by the kind's language-neutral fallback.
    """

    def configure(self, binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[CodeSuite])
        binder.multibind(dict[str, BaseUnitExtractor[DispatchedFile]], to={})
        binder.multibind(
            dict[str, BaseFileMetadataExtractor],
            to={python.SUITE_LANGUAGE: PythonFileMetadataExtractor},
        )
        binder.multibind(
            dict[str, BaseDirectoryUnitFactory],
            to={python.SUITE_LANGUAGE: PythonPackageUnitFactory},
        )

    @provider
    def provide_file_contents_extractor(
        self,
        language_to_unit_extractor: dict[str, BaseUnitExtractor[DispatchedFile]],
        file_traits_identifier: BaseFileTraitsIdentifier,
    ) -> FileContentsExtractor:
        return FileContentsExtractor(
            TraitsBasedExtractionDelegator(
                language_to_unit_extractor,
                fallback_extractor=WholeFileExtractor(),
                file_traits_identifier=file_traits_identifier,
            )
        )

    @provider
    def provide_project_extractor(
        self,
        language_to_file_metadata_extractor: dict[str, BaseFileMetadataExtractor],
        language_to_directory_unit_factory: dict[str, BaseDirectoryUnitFactory],
        file_traits_identifier: BaseFileTraitsIdentifier,
    ) -> RecursiveProjectExtractor:
        return RecursiveProjectExtractor(
            TraitsBasedExtractionDelegator(
                language_to_file_metadata_extractor,
                fallback_extractor=LanguageNeutralFileMetadataExtractor(),
                file_traits_identifier=file_traits_identifier,
            ),
            TraitsBasedExtractionDelegator(
                language_to_directory_unit_factory,
                fallback_extractor=LanguageNeutralDirectoryUnitFactory(),
            ),
        )
