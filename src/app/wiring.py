"""Builds klint's object graph from the settings."""

from typing import Callable, NewType, Union

from injector import Binder, Injector, Module, provider, singleton

from src import catalog
from src.app.settings import AppSettings
from src.app.usecases.audit_path import AuditPath
from src.catalog.code.common.extractors.fallback_file_metadata import (
    FallbackFileMetadataExtractor,
)
from src.catalog.code.common.extractors.project import RecursiveProjectExtractor
from src.catalog.code.python.extractors.file_metadata import (
    PythonFileMetadataExtractor,
)
from src.catalog.code.python.extractors.package_factory import (
    PythonPackageUnitFactory,
)
from src.catalog.common.extractors.file_collector import (
    collect_target_directories,
    collect_target_files,
)
from src.catalog.common.extractors.whole_file import WholeFileExtractor
from src.catalog.common.scales.pass_fail import PASS_FAIL_SCALE
from src.core.auditor import Auditor
from src.core.interfaces.judge import BaseJudge
from src.core.models.scale import AnswerScale
from src.core.registry import UnitRegistry
from src.infra.rule_loader.json_loader import JsonRuleLoader
from src.infra.system_one.remote import RemoteSystemOneJudge

# One auditor and one use case per kind of audit, told apart by these keys.
FileAuditor = NewType("FileAuditor", Auditor)
ProjectAuditor = NewType("ProjectAuditor", Auditor)
FileAuditPath = NewType("FileAuditPath", AuditPath)
ProjectAuditPath = NewType("ProjectAuditPath", AuditPath)

Override = Union[Module, Callable[[Binder], None]]


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
    def provide_project_extractor(self) -> RecursiveProjectExtractor:
        return RecursiveProjectExtractor(
            file_extractors=(
                PythonFileMetadataExtractor(),
                FallbackFileMetadataExtractor(),
            ),
            directory_factory=PythonPackageUnitFactory(),
        )

    @singleton
    @provider
    def provide_file_auditor(
        self,
        settings: AppSettings,
        judge: BaseJudge,
        registry: UnitRegistry,
        scale: AnswerScale,
    ) -> FileAuditor:
        return FileAuditor(
            Auditor(
                extractor=WholeFileExtractor(),
                judge=judge,
                rule_loader=JsonRuleLoader(settings.default_rules_paths, registry),
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
        extractor: RecursiveProjectExtractor,
    ) -> ProjectAuditor:
        if not settings.default_project_rules_paths:
            raise EnvironmentError(
                "KEV_DEFAULT_PROJECT_RULES_PATH must be set to use the project "
                "structure audit CLI (src/cli/project_audit.py)."
            )
        return ProjectAuditor(
            Auditor(
                extractor=extractor,
                judge=judge,
                rule_loader=JsonRuleLoader(
                    settings.default_project_rules_paths, registry
                ),
                scale=scale,
            )
        )

    @singleton
    @provider
    def provide_file_audit_path(self, auditor: FileAuditor) -> FileAuditPath:
        return FileAuditPath(AuditPath(auditor, collect_target_files))

    @singleton
    @provider
    def provide_project_audit_path(self, auditor: ProjectAuditor) -> ProjectAuditPath:
        return ProjectAuditPath(
            AuditPath(auditor, collect_target_directories, whole_tree=True)
        )


def create_injector(settings: AppSettings, *overrides: Override) -> Injector:
    """Return an injector for ``settings``; overrides replace individual bindings."""
    return Injector([KlintModule(settings), *overrides])


def create_file_audit_path(settings: AppSettings, *overrides: Override) -> AuditPath:
    return create_injector(settings, *overrides).get(FileAuditPath)


def create_project_audit_path(
    settings: AppSettings, *overrides: Override
) -> AuditPath:
    return create_injector(settings, *overrides).get(ProjectAuditPath)
