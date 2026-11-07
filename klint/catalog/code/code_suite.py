"""The code suite and the injector module that adds it to an audit."""

from injector import Binder, Module, ProviderOf, inject, provider

from klint.catalog.code.language_neutral import (
    CODE_IGNORED_NAMES,
    PRACTICE_SCALE,
    AuditableDirectoryUnit,
    AuditableFileMetadataUnit,
    DirectoryRenderer,
    FileMetadataRenderer,
)
from klint.catalog.code.language_neutral.extraction import (
    BaseDirectoryUnitFactory,
    BaseFileMetadataExtractor,
    DirectoryTreeExtractor,
    FileContentsExtractor,
    LanguageNeutralDirectoryUnitFactory,
    LanguageNeutralFileMetadataExtractor,
    ProjectStructureExtractor,
)
from klint.catalog.code.python import (
    SUITE_LANGUAGE,
    AuditablePythonClassUnit,
    AuditablePythonFunctionUnit,
    AuditablePythonPackageUnit,
    PythonClassRenderer,
    PythonFileMetadataExtractor,
    PythonFunctionRenderer,
    PythonPackageRenderer,
    PythonPackageUnitFactory,
    PythonSourceFileExtractor,
)
from klint.catalog.domain_neutral import (
    AuditableFileUnit,
    DirectoryTreeSourceFactory,
    WholeFileRenderer,
)
from klint.catalog.domain_neutral.extraction import (
    DispatchedFile,
    TraitsBasedExtractionDelegator,
    WholeFileExtractor,
)
from klint.core import UnitRegistry
from klint.core.interfaces import (
    AuditKind,
    BaseFileTraitsIdentifier,
    BaseRuleLoader,
    BaseSuite,
    BaseUnitExtractor,
    UnitSource,
)
from klint.core.models.audits import AuditInputKind

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
                unit_class_to_renderer={
                    AuditableFileUnit: WholeFileRenderer(),
                    AuditablePythonClassUnit: PythonClassRenderer(),
                    AuditablePythonFunctionUnit: PythonFunctionRenderer(),
                },
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
        registry.register_unit(AuditablePythonClassUnit)
        registry.register_unit(AuditablePythonFunctionUnit)


class CodeSuiteModule(Module):
    """Adds the code suite to an audit, with what handles each language.

    Each kind of audit picks what handles a file or directory by its traits,
    from the bindings for each language here. A language with nothing bound
    is handled by the kind's language-neutral fallback.
    """

    def configure(self, binder: Binder) -> None:
        binder.multibind(list[BaseSuite], to=[CodeSuite])
        binder.multibind(
            dict[str, BaseUnitExtractor[DispatchedFile]],
            to={SUITE_LANGUAGE: PythonSourceFileExtractor},
        )
        binder.multibind(
            dict[str, BaseFileMetadataExtractor],
            to={SUITE_LANGUAGE: PythonFileMetadataExtractor},
        )
        binder.multibind(
            dict[str, BaseDirectoryUnitFactory],
            to={SUITE_LANGUAGE: PythonPackageUnitFactory},
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
    def provide_directory_tree_extractor(
        self,
        language_to_file_metadata_extractor: dict[str, BaseFileMetadataExtractor],
        language_to_directory_unit_factory: dict[str, BaseDirectoryUnitFactory],
        file_traits_identifier: BaseFileTraitsIdentifier,
    ) -> DirectoryTreeExtractor:
        return DirectoryTreeExtractor(
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
