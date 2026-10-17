"""Binds what klint's constructors cannot state themselves.

Each class asks for what it needs with @inject. What is left here is what
its signature cannot express: the settings, what is chosen from them, and
which implementation stands for each language.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NewType

from injector import Binder, Injector, Module, multiprovider, provider, singleton

from src import catalog
from src.app.audit_mode import AuditMode
from src.app.settings import AppSettings
from src.catalog.code import python as python_suite
from src.catalog.code.common.extractors.directory_factory import (
    BaseDirectoryUnitFactory,
)
from src.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
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
from src.catalog.common.scanners.target_scanner import IgnoredNames
from src.core.interfaces.extractor import BaseUnitExtractor
from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from src.core.interfaces.judge import BaseJudge
from src.core.interfaces.rule_loader import BaseRuleLoader
from src.core.models.scale import AnswerScale
from src.core.registry import UnitRegistry
from src.infra.language_to_file_extensions_loader.json_loader import (
    load_file_extension_to_language,
)
from src.infra.rule_loader.json_loader import JsonRuleLoader
from src.infra.system_one.remote import RemoteSystemOneJudge

# The language each file extension stands for, loaded once per injector.
FileExtensionToLanguage = NewType("FileExtensionToLanguage", Mapping[str, str])

Override = Module | Callable[[Binder], None]


class KlintModule(Module):
    """Binds everything an audit needs that one AppSettings decides."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def configure(self, binder: Binder) -> None:
        binder.bind(AppSettings, to=self._settings)
        # One answer scale for now; it is meant to vary by suite.
        binder.bind(AnswerScale, to=PASS_FAIL_SCALE)
        binder.bind(IgnoredNames, to=CODE_IGNORED_NAMES)
        # What handles each language, looked up by the traits of each file. A
        # language not listed is handled in a language-neutral way.
        binder.multibind(dict[str, BaseUnitExtractor], to={})
        binder.multibind(
            dict[str, BaseFileMetadataExtractor],
            to={python_suite.SUITE_LANGUAGE: PythonFileMetadataExtractor},
        )
        binder.multibind(
            dict[str, BaseDirectoryUnitFactory],
            to={python_suite.SUITE_LANGUAGE: PythonPackageUnitFactory},
        )

    @singleton
    @provider
    def provide_language_neutral_unit_extractor(self) -> BaseUnitExtractor:
        # Reads a file in the file contents audit when its language has no
        # extractor of its own: as one whole file.
        return WholeFileExtractor()

    @singleton
    @provider
    def provide_unit_registry(self) -> UnitRegistry:
        registry = UnitRegistry()
        catalog.register(registry)
        return registry

    @singleton
    @provider
    def provide_judge(self, settings: AppSettings) -> BaseJudge:
        # A single binding, so that the remote mode never loads the model.
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
    @multiprovider
    def provide_audit_mode_to_rule_loader(
        self,
        settings: AppSettings,
        registry: UnitRegistry,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> dict[AuditMode, BaseRuleLoader]:
        known_languages = set(file_extension_to_language.values())
        built_in_rule_loader = JsonRuleLoader(
            settings.built_in_rule_packs,
            settings.fallback_rule_packs,
            registry,
            known_languages,
        )

        def choose_rule_loader(rule_pack_override: Path | None) -> BaseRuleLoader:
            if rule_pack_override is None:
                return built_in_rule_loader
            # The file replaces every built-in pack, the fallback ones too, so
            # its rules are asked about every file.
            return JsonRuleLoader(
                (rule_pack_override,),
                (rule_pack_override,),
                registry,
                known_languages,
            )

        return {
            AuditMode.FILE_CONTENTS: choose_rule_loader(
                settings.file_contents_rule_pack_override
            ),
            AuditMode.PROJECT_STRUCTURE: choose_rule_loader(
                settings.project_structure_rule_pack_override
            ),
        }


def create_injector(settings: AppSettings, *overrides: Override) -> Injector:
    """Return an injector for ``settings``; overrides replace individual bindings."""
    return Injector([KlintModule(settings), *overrides])
