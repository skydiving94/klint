"""Builds klint's object graph from the settings."""

from collections.abc import Callable, Mapping
from typing import NewType

from injector import Binder, Injector, Module, provider, singleton

from src import catalog
from src.app.audit_mode import AuditMode
from src.app.audit_pipeline import AuditPipeline
from src.app.settings import AppSettings
from src.app.usecases.audit_path import AuditPath
from src.catalog.code import python as python_suite
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.common.extractors.traits_based_extraction_delegator import (
    TraitsBasedExtractionDelegator,
)
from src.catalog.code.common.ignored_names import CODE_IGNORED_NAMES
from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.catalog.common.scanners.target_scanner import TargetScanner
from src.core.auditor import Auditor
from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from src.core.interfaces.judge import BaseJudge
from src.core.models.scale import AnswerScale
from src.core.registry import UnitRegistry
from src.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from src.infra.rule_loader.json_loader import JsonRuleLoader
from src.infra.system_one.remote import RemoteSystemOneJudge

# One auditor and one use case per kind of audit, told apart by these keys.
FileAuditor = NewType("FileAuditor", Auditor)
ProjectAuditor = NewType("ProjectAuditor", Auditor)
FileAuditPath = NewType("FileAuditPath", AuditPath)
ProjectAuditPath = NewType("ProjectAuditPath", AuditPath)
# The language each file extension stands for, loaded once per injector.
FileExtensionToLanguage = NewType("FileExtensionToLanguage", Mapping[str, str])

Override = Module | Callable[[Binder], None]


class KlintModule(Module):
    """Provides everything an audit needs, built from one AppSettings."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    @singleton
    @provider
    def provide_settings(self) -> AppSettings:
        return self._settings

    @singleton
    @provider
    def provide_unit_registry(self) -> UnitRegistry:
        registry = UnitRegistry()
        catalog.register(registry)
        return registry

    @singleton
    @provider
    def provide_scale(self) -> AnswerScale:
        return PASS_FAIL_SCALE

    @singleton
    @provider
    def provide_judge(self, settings: AppSettings) -> BaseJudge:
        if settings.kev_mode == "local":
            from src.infra.system_one.local import LocalKevJudge

            return LocalKevJudge(checkpoint=settings.model_name)
        return RemoteSystemOneJudge(
            model_name=settings.model_name,
            base_url=settings.kev_base_url,
            api_key=settings.kev_api_key,
        )

    @singleton
    @provider
    def provide_file_extension_to_language(
        self, settings: AppSettings
    ) -> FileExtensionToLanguage:
        return FileExtensionToLanguage(
            load_file_extension_to_language(settings.language_to_file_extensions_path)
        )

    @singleton
    @provider
    def provide_file_traits_identifier(
        self, file_extension_to_language: FileExtensionToLanguage
    ) -> BaseFileTraitsIdentifier:
        return ExtensionFileTraitsIdentifier(file_extension_to_language)

    @singleton
    @provider
    def provide_target_scanner(
        self, file_traits_identifier: BaseFileTraitsIdentifier
    ) -> TargetScanner:
        return TargetScanner(file_traits_identifier, CODE_IGNORED_NAMES)

    @singleton
    @provider
    def provide_project_extractor(self) -> RecursiveProjectExtractor:
        # What handles each language in the project audit. A language not
        # listed here is handled in a language-neutral way.
        delegator = TraitsBasedExtractionDelegator(
            language_to_file_metadata_extractor={
                python_suite.SUITE_LANGUAGE: PythonFileMetadataExtractor(),
            },
            language_to_directory_unit_factory={
                python_suite.SUITE_LANGUAGE: PythonPackageUnitFactory(),
            },
        )
        return RecursiveProjectExtractor(delegator)

    @singleton
    @provider
    def provide_audit_pipeline(
        self,
        target_scanner: TargetScanner,
        project_extractor: RecursiveProjectExtractor,
    ) -> AuditPipeline:
        return AuditPipeline(
            target_scanner=target_scanner,
            # What extracts the units of each language in the file contents
            # audit. A language not listed here is read as one whole file.
            language_to_unit_extractor={},
            language_neutral_unit_extractor=WholeFileExtractor(),
            project_extractor=project_extractor,
        )

    @singleton
    @provider
    def provide_file_auditor(
        self,
        settings: AppSettings,
        judge: BaseJudge,
        registry: UnitRegistry,
        scale: AnswerScale,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> FileAuditor:
        return FileAuditor(
            Auditor(
                judge=judge,
                rule_loader=JsonRuleLoader(
                    settings.default_rules_paths,
                    registry,
                    known_languages=set(file_extension_to_language.values()),
                ),
                scale=scale,
            )
        )

    @singleton
    @provider
    def provide_project_auditor(
        self,
        settings: AppSettings,
        judge: BaseJudge,
        registry: UnitRegistry,
        scale: AnswerScale,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> ProjectAuditor:
        if not settings.default_project_rules_paths:
            raise OSError(
                "KEV_DEFAULT_PROJECT_RULES_PATH must be set to use the project "
                "structure audit CLI (src/cli/project_audit.py)."
            )
        return ProjectAuditor(
            Auditor(
                judge=judge,
                rule_loader=JsonRuleLoader(
                    settings.default_project_rules_paths,
                    registry,
                    known_languages=set(file_extension_to_language.values()),
                ),
                scale=scale,
            )
        )

    @singleton
    @provider
    def provide_file_audit_path(
        self, auditor: FileAuditor, audit_pipeline: AuditPipeline
    ) -> FileAuditPath:
        return FileAuditPath(
            AuditPath(auditor, audit_pipeline, AuditMode.FILE_CONTENTS)
        )

    @singleton
    @provider
    def provide_project_audit_path(
        self, auditor: ProjectAuditor, audit_pipeline: AuditPipeline
    ) -> ProjectAuditPath:
        return ProjectAuditPath(
            AuditPath(auditor, audit_pipeline, AuditMode.PROJECT_STRUCTURE)
        )


def create_injector(settings: AppSettings, *overrides: Override) -> Injector:
    """Return an injector for ``settings``; overrides replace individual bindings."""
    return Injector([KlintModule(settings), *overrides])


def create_file_audit_path(settings: AppSettings, *overrides: Override) -> AuditPath:
    return create_injector(settings, *overrides).get(FileAuditPath)


def create_project_audit_path(settings: AppSettings, *overrides: Override) -> AuditPath:
    return create_injector(settings, *overrides).get(ProjectAuditPath)
