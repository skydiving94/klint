"""Binds what klint's constructors cannot state themselves.

Each class asks for what it needs with @inject. What is left here is what
its signature cannot express: the settings and what is chosen from them.
The suites an audit draws on are added by the caller; each one binds what
it needs itself.
"""

import warnings
from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import replace
from pathlib import Path
from typing import NewType, assert_never

from injector import Binder, Injector, Module, provider, singleton

from klint.app.audit_kind_registry import AuditKindRegistry
from klint.app.judge_mode import JudgeMode
from klint.app.settings import AppSettings
from klint.catalog.domain_neutral.file_traits_identifiers.extension_identifier import (
    ExtensionFileTraitsIdentifier,
)
from klint.catalog.domain_neutral.file_traits_identifiers.overriding_identifier import (
    OverridingFileTraitsIdentifier,
)
from klint.catalog.domain_neutral.file_traits_identifiers.tag_detecting_identifier import (  # noqa: E501
    TagDetectingFileTraitsIdentifier,
)
from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.interfaces.judge import BaseJudge
from klint.core.interfaces.rule_loader import BaseRuleLoader
from klint.core.interfaces.rule_source import BaseRuleSource
from klint.core.interfaces.suite import BaseSuite
from klint.core.klint_warning import KlintWarning
from klint.core.models.audit_kind import AuditKind
from klint.core.models.file_traits_override import FileTraitsOverride
from klint.core.registry import UnitRegistry
from klint.infra.language_to_file_extensions_loader.language_table_loader import (
    load_file_extension_to_language,
)
from klint.infra.rule_loader.json_file_rule_source import JsonFileRuleSource
from klint.infra.rule_loader.rule_pack_loader import RulePackLoader
from klint.infra.system_one.remote import RemoteSystemOneJudge
from klint.infra.tag_detection_loader.tag_table_loader import load_tag_detection_table

# The language each file extension stands for, loaded once per injector.
FileExtensionToLanguage = NewType("FileExtensionToLanguage", Mapping[str, str])

Override = Module | Callable[[Binder], None]


class KlintModule(Module):
    """Binds everything an audit needs that one AppSettings decides.

    kind_id_to_rule_pack_override names, for a kind of audit, one file that
    replaces every built-in pack, the fallback ones too, so that its rules
    are asked about every unit of that kind.
    """

    def __init__(
        self,
        settings: AppSettings,
        kind_id_to_rule_pack_override: Mapping[str, Path],
    ) -> None:
        self._settings = settings
        self._kind_id_to_rule_pack_override = dict(kind_id_to_rule_pack_override)

    def configure(self, binder: Binder) -> None:
        binder.bind(AppSettings, to=self._settings)
        # The suites an audit can draw on; each one adds itself.
        binder.multibind(list[BaseSuite], to=[])

    @singleton
    @provider
    def provide_unit_registry(self, suites: list[BaseSuite]) -> UnitRegistry:
        registry = UnitRegistry()
        for suite in suites:
            suite.register_unit_types(registry)
        return registry

    @singleton
    @provider
    def provide_judge(self, settings: AppSettings) -> BaseJudge:
        # A single binding, so that the remote mode never loads the model.
        match settings.judge_mode:
            case JudgeMode.LOCAL:
                from klint.infra.system_one.local import LocalKevJudge

                return LocalKevJudge(checkpoint=settings.model_name)
            case JudgeMode.REMOTE:
                return RemoteSystemOneJudge(
                    model_name=settings.model_name,
                    base_url=settings.judge_base_url,
                    api_key=settings.judge_api_key,
                )
            case _:
                assert_never(settings.judge_mode)

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
        self, settings: AppSettings, file_extension_to_language: FileExtensionToLanguage
    ) -> BaseFileTraitsIdentifier:
        # The language from the extension and the tags the file shows, then
        # what the project's klint.json says over them.
        _warn_about_unknown_override_languages(
            settings.file_traits_overrides, set(file_extension_to_language.values())
        )
        return OverridingFileTraitsIdentifier(
            TagDetectingFileTraitsIdentifier(
                ExtensionFileTraitsIdentifier(file_extension_to_language),
                load_tag_detection_table(settings.tag_detection_path),
            ),
            settings.file_traits_overrides,
        )

    @singleton
    @provider
    def provide_rule_loader(
        self,
        settings: AppSettings,
        registry: UnitRegistry,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> BaseRuleLoader:
        # The built-in packs, chosen by the traits of each unit.
        return RulePackLoader(
            _create_rule_sources(settings.built_in_rule_packs),
            _create_rule_sources(settings.fallback_rule_packs),
            registry,
            set(file_extension_to_language.values()),
            project_rule_sources=_create_rule_sources(settings.project_rule_packs),
        )

    @singleton
    @provider
    def provide_audit_kind_registry(
        self,
        settings: AppSettings,
        suites: list[BaseSuite],
        registry: UnitRegistry,
        file_extension_to_language: FileExtensionToLanguage,
    ) -> AuditKindRegistry:
        known_languages = set(file_extension_to_language.values())

        def apply_rule_pack_override(audit_kind: AuditKind) -> AuditKind:
            rule_pack_override = self._kind_id_to_rule_pack_override.get(
                audit_kind.kind_id
            )
            if rule_pack_override is None:
                return audit_kind
            override_sources = _create_rule_sources((rule_pack_override,))
            return replace(
                audit_kind,
                rule_loader=RulePackLoader(
                    override_sources,
                    override_sources,
                    registry,
                    known_languages,
                    project_rule_sources=_create_rule_sources(
                        settings.project_rule_packs
                    ),
                ),
            )

        return AuditKindRegistry(
            [
                apply_rule_pack_override(audit_kind)
                for suite in suites
                for audit_kind in suite.list_audit_kinds()
            ]
        )


def _warn_about_unknown_override_languages(
    file_traits_overrides: Sequence[FileTraitsOverride], known_languages: Set[str]
) -> None:
    """Warn about each override that names a language no file is identified as."""
    for override in file_traits_overrides:
        if override.language is not None and override.language not in known_languages:
            warnings.warn(
                f"The file_traits entry for '{override.glob}' names unknown "
                f"language '{override.language}', so no pack limited to "
                f"languages loads for its files; known languages: "
                f"{sorted(known_languages)}",
                KlintWarning,
                stacklevel=2,
            )


def _create_rule_sources(rule_packs: Sequence[Path]) -> list[BaseRuleSource]:
    """Return a source for each rules file; a file that does not exist has none."""
    return [JsonFileRuleSource(path) for path in rule_packs]


def create_injector(
    settings: AppSettings,
    *overrides: Override,
    kind_id_to_rule_pack_override: Mapping[str, Path] | None = None,
) -> Injector:
    """Return an injector for ``settings``; overrides add or replace bindings.

    No suite is added: an override adds each one the audit draws on.
    kind_id_to_rule_pack_override is as KlintModule takes it.
    """
    return Injector(
        [KlintModule(settings, kind_id_to_rule_pack_override or {}), *overrides]
    )
